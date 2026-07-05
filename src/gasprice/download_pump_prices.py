"""
Module: download_pump_prices.py
Description: Resilient, idempotent downloader for Tankerkönig historical fuel price data.
             Downloads daily price CSVs and converts them to compressed Parquet on the fly.
             If interrupted, re-running the script skips already-downloaded days.
"""

import polars as pl
import requests
from requests.exceptions import RequestException
import hashlib
import json
import os
import sys
import time
import logging
from datetime import date, timedelta, datetime
from pathlib import Path

# ==========================================
# 1. SETUP & CONFIGURATION
# ==========================================

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("gasprice.download_pump_prices")

# ==========================================
# 1b. MANIFEST / HASH HELPERS
# ==========================================

def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def _load_manifest(manifest_path: Path) -> dict:
    if not manifest_path.exists():
        return {}
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _save_manifest(manifest_path: Path, manifest: dict) -> None:
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

def _median_recent_rows(manifest: dict, current_date: date, lookback_days: int = 7) -> int | None:
    """
    Compute the median row count of completed daily files before current_date.
    Returns None if there are fewer than 3 historical files to compare against.
    """
    past_rows = []
    for d in sorted(manifest.keys()):
        try:
            entry_date = date.fromisoformat(d)
        except (ValueError, TypeError):
            continue
        if entry_date >= current_date:
            continue
        rows = manifest[d].get("rows", 0)
        if rows and rows > 0:
            past_rows.append(rows)

    if len(past_rows) < 3:
        return None

    recent = past_rows[-lookback_days:]
    recent_sorted = sorted(recent)
    n = len(recent_sorted)
    if n % 2 == 1:
        return recent_sorted[n // 2]
    return (recent_sorted[n // 2 - 1] + recent_sorted[n // 2]) // 2


def _is_file_complete(
    df: pl.DataFrame,
    file_date: date,
    manifest: dict,
    lookback_days: int = 7,
    threshold: float = 0.5,
) -> bool:
    """
    Heuristic completeness check for a daily Tankerkönig price file.
    Compares the file's row count against the median of the last lookback_days
    completed files. If it is significantly smaller, we treat it as potentially
    incomplete and re-fetch it on the next run.
    """
    if df.is_empty():
        return False

    median_rows = _median_recent_rows(manifest, file_date, lookback_days)
    if median_rows is None:
        # Not enough history yet; trust the file if it is non-empty.
        return True

    return df.height >= threshold * median_rows

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data" / "tankerkoenig"
PRICES_DIR = DATA_DIR / "prices"
STATIONS_DIR = DATA_DIR / "stations"
MANIFEST_FILE = PRICES_DIR / ".download_manifest.json"
STATIONS_MANIFEST_FILE = STATIONS_DIR / ".download_manifest.json"

# How many days before today do we always re-download/verify?
# This catches delayed/backfilled data and partial daily files.
RECENT_DAYS = 7

# Date range to download
START_DATE = date(2021, 1, 1)
END_DATE = date.today()

# For quick testing: set True to only download 3 days
TEST_MODE = "--test" in sys.argv

# ANSI escape codes for modern startup-style CLI
C_GREEN = "\033[1;92m"
C_YELLOW = "\033[1;93m"
C_RED = "\033[1;91m"
C_CYAN = "\033[1;96m"
C_RESET = "\033[0m"

def log_success(msg: str):
    print(f"{C_GREEN}[✔] SUCCESS:{C_RESET} {msg}")

def log_warn(msg: str):
    print(f"{C_YELLOW}[▲] WARNING:{C_RESET} {msg}")

def log_error(msg: str):
    print(f"{C_RED}[✘] ERROR:{C_RESET} {msg}")

def log_info(msg: str):
    print(f"{C_CYAN}[ℹ] INFO:{C_RESET} {msg}")

# ==========================================
# 2. CREDENTIAL LOADING
# ==========================================

def load_env():
    """Load credentials from .env file."""
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        log_error(f"{env_path} not found. Create it with TK_USER and TK_PASS.")
        sys.exit(1)

    env = {}
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, val = line.split("=", 1)
            env[key.strip()] = val.strip()

    return env["TK_USER"], env["TK_PASS"], env["TK_BASE_URL"]

# ==========================================
# 3. DOWNLOAD ENGINE
# ==========================================

def download_csv(session: requests.Session, url: str, max_retries: int = 3, backoff_factor: int = 2) -> str | None:
    """
    Downloads a CSV from the given URL with exponential backoff retry.
    Returns the raw text content, or None if the file doesn't exist (404).
    """
    for attempt in range(1, max_retries + 1):
        try:
            resp = session.get(url, timeout=120)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.text
        except RequestException as e:
            if attempt < max_retries:
                wait = backoff_factor ** attempt
                print(f"  {C_YELLOW}[▲] WARNING:{C_RESET} Connection error (attempt {attempt}/{max_retries}), retrying in {wait}s...")
                time.sleep(wait)
            else:
                print(f"  {C_RED}[✘] ERROR:{C_RESET} Failed after {max_retries} attempts: {e}")
                raise

def download_stations(session: requests.Session, base_url: str):
    """Download the latest stations metadata file, re-downloading if the upstream content changed."""
    STATIONS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = STATIONS_DIR / "latest-stations.parquet"
    manifest = _load_manifest(STATIONS_MANIFEST_FILE)

    # Try today, yesterday, day before yesterday
    for d in [date.today(), date.today() - timedelta(days=1), date.today() - timedelta(days=2)]:
        url = f"{base_url}/stations/{d.year}/{d.month:02d}/{d.strftime('%Y-%m-%d')}-stations.csv"
        log_info(f"Trying stations file for {d}...")
        try:
            csv_text = download_csv(session, url)
            if csv_text:
                file_hash = _sha256_text(csv_text)
                cached_hash = manifest.get("latest-stations.csv", {}).get("sha256")
                if output_path.exists() and cached_hash == file_hash:
                    log_success(f"Stations file unchanged: {output_path}")
                    return
                break
        except RequestException:
            continue
    else:
        log_error("Could not find a recent stations file. Skipping.")
        return

    # Use today's or yesterday's stations file
    for d in [date.today(), date.today() - timedelta(days=1), date.today() - timedelta(days=2)]:
        url = f"{base_url}/stations/{d.year}/{d.month:02d}/{d.strftime('%Y-%m-%d')}-stations.csv"
        log_info(f"Trying stations file for {d}...")
        try:
            csv_text = download_csv(session, url)
            if csv_text:
                break
        except RequestException:
            continue
    else:
        log_error("Could not find a recent stations file. Skipping.")
        return

    # Parse with Polars — stations CSV has messy quoting due to JSON column
    from io import StringIO
    try:
        df = pl.read_csv(
            StringIO(csv_text),
            infer_schema_length=10000,
            ignore_errors=True,
        )
    except Exception as e:
        log_error(f"Failed to parse stations CSV file: {e}")
        raise e

    df.write_parquet(output_path, compression="zstd")
    file_hash = _sha256_text(csv_text)
    manifest["latest-stations.csv"] = {
        "sha256": file_hash,
        "rows": df.height,
        "downloaded_at": datetime.now().isoformat(),
    }
    _save_manifest(STATIONS_MANIFEST_FILE, manifest)
    log_success(f"Stations saved: {output_path} ({df.height:,} stations, {output_path.stat().st_size / 1024:.0f} KB)")

def download_prices(
    session: requests.Session,
    base_url: str,
    start_date: date | None = None,
    end_date: date | None = None,
):
    """Download daily price files for the configured date range."""
    current = start_date or START_DATE
    end = end_date or END_DATE

    if TEST_MODE:
        end = min(current + timedelta(days=2), END_DATE)
        log_info(f"TEST MODE: downloading only {current} to {end}")

    total_days = (end - current).days + 1
    downloaded = 0
    skipped = 0
    updated = 0
    failed = 0
    failed_dates = []
    last_successful_date = None
    manifest = _load_manifest(MANIFEST_FILE)

    log_info(f"Downloading prices: {current} → {end} ({total_days} days)")
    print("=" * 60)

    while current <= end:
        year_dir = PRICES_DIR / str(current.year)
        year_dir.mkdir(parents=True, exist_ok=True)
        output_path = year_dir / f"{current.strftime('%Y-%m-%d')}.parquet"

        day_num = (current - (start_date or START_DATE)).days + 1

        # Skip if already downloaded, content hash is unchanged, and the file
        # was previously marked complete. Always re-verify the last RECENT_DAYS
        # to catch delayed/backfilled data or partial daily files.
        is_recent = current >= (end - timedelta(days=RECENT_DAYS))
        date_key = str(current)
        cached_entry = manifest.get(date_key, {})

        was_complete = cached_entry.get("complete", False)
        if (
            output_path.exists()
            and not is_recent
            and cached_entry.get("sha256")
            and was_complete
        ):
            skipped += 1
            last_successful_date = current
            current += timedelta(days=1)
            continue

        url = f"{base_url}/prices/{current.year}/{current.month:02d}/{current.strftime('%Y-%m-%d')}-prices.csv"
        progress = f"[{day_num}/{total_days}]"

        try:
            csv_text = download_csv(session, url)
            if csv_text is None:
                print(f"  {C_YELLOW}[▲] {progress} {current}:{C_RESET} 404 (no data)")
                failed += 1
                failed_dates.append(str(current))
                current += timedelta(days=1)
                continue

            # Parse CSV → Parquet in one shot
            from io import StringIO
            try:
                df = pl.read_csv(StringIO(csv_text), try_parse_dates=True)
            except Exception as parse_err:
                log_error(f"Failed to parse price CSV for {current}: {parse_err}")
                raise parse_err
                
            df.write_parquet(output_path, compression="zstd")

            file_hash = _sha256_text(csv_text)
            is_complete = _is_file_complete(df, current, manifest)
            manifest[date_key] = {
                "sha256": file_hash,
                "rows": df.height,
                "complete": is_complete,
                "downloaded_at": datetime.now().isoformat(),
            }

            size_kb = output_path.stat().st_size / 1024
            if cached_entry.get("sha256") == file_hash:
                updated += 1
                status = f"{C_GREEN}[✔] {progress} {current}:{C_RESET} {df.height:,} rows, {size_kb:.0f} KB (verified unchanged)"
            elif not is_complete:
                downloaded += 1
                status = f"{C_YELLOW}[▲] {progress} {current}:{C_RESET} {df.height:,} rows, {size_kb:.0f} KB (incomplete — will retry)"
            else:
                downloaded += 1
                status = f"{C_GREEN}[✔] {progress} {current}:{C_RESET} {df.height:,} rows, {size_kb:.0f} KB"
            last_successful_date = current
            print(status)

        except RequestException as e:
            log_error(f"Network error downloading prices for {current}: {e}")
            raise e
        except Exception as e:
            log_error(f"Format/disk error processing prices for {current}: {e}")
            raise e

        current += timedelta(days=1)

    _save_manifest(MANIFEST_FILE, manifest)

    print("\n" + "=" * 60)
    print(f"Done! Downloaded: {downloaded}, Updated/Verified: {updated}, Skipped (unchanged): {skipped}, Failed: {failed}")
    if failed_dates:
        print(f"Failed dates (No data available yet): {', '.join(failed_dates)}")

    today = date.today()
    if last_successful_date:
        delay_days = (today - last_successful_date).days
        print(f"\nDATA FRESHNESS REPORT:")
        print(f"Current System Date:  {today}")
        print(f"Last Available Data:  {last_successful_date}")
        if delay_days == 0:
            print("Status: Up to date (No delay!)")
        else:
            print(f"Status: Data source is {delay_days} day(s) behind the current date.")
    else:
        print("No successful downloads found.")

if __name__ == "__main__":
    user, password, base_url = load_env()

    # Optional CLI override for the start/end dates (useful for backfills).
    start_override = None
    if "--start-date" in sys.argv:
        idx = sys.argv.index("--start-date")
        try:
            start_override = date.fromisoformat(sys.argv[idx + 1])
        except (IndexError, ValueError):
            log_error("Usage: --start-date YYYY-MM-DD")
            sys.exit(1)

    end_override = None
    if "--end-date" in sys.argv:
        idx = sys.argv.index("--end-date")
        try:
            end_override = date.fromisoformat(sys.argv[idx + 1])
        except (IndexError, ValueError):
            log_error("Usage: --end-date YYYY-MM-DD")
            sys.exit(1)

    session = requests.Session()
    session.auth = (user, password)
    session.headers.update({"User-Agent": "TankAnalysis/1.0"})

    effective_start = start_override or START_DATE
    effective_end = end_override or END_DATE
    print(f"Tankerkönig Data Downloader")
    print(f"Target: {DATA_DIR}")
    print(f"Range:  {effective_start} → {effective_end}")
    if TEST_MODE:
        print("Mode:   ⚡ TEST (3 days only)")
    print()

    print("--- Downloading Stations Metadata ---")
    download_stations(session, base_url)

    print("\n--- Downloading Daily Prices ---")
    download_prices(session, base_url, start_date=start_override, end_date=end_override)
