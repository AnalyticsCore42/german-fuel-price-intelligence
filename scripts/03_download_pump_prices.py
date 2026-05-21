"""
Script: 04_download_tankerkoenig.py
Description: Resilient, idempotent downloader for Tankerkönig historical fuel price data.
             Downloads daily price CSVs and converts them to compressed Parquet on the fly.
             If interrupted, re-running the script skips already-downloaded days.
Inputs:  ../.env (credentials)
Outputs: ../data/tankerkoenig/prices/YYYY/YYYY-MM-DD.parquet
         ../data/tankerkoenig/stations/latest-stations.parquet

Memory Constraint: Each daily CSV (~25 MB, ~417k rows) is loaded, compressed, and freed
                   before the next day is fetched. Peak RAM usage: ~50 MB.
"""

import polars as pl
import requests
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path

# ==========================================
# 1. SETUP & CONFIGURATION
# ==========================================

SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
DATA_DIR = PROJECT_DIR / "data" / "tankerkoenig"
PRICES_DIR = DATA_DIR / "prices"
STATIONS_DIR = DATA_DIR / "stations"

# Date range to download
START_DATE = date(2021, 1, 1)
END_DATE = date.today()

# For quick testing: set True to only download 3 days
TEST_MODE = "--test" in sys.argv

# ==========================================
# 2. CREDENTIAL LOADING
# ==========================================

def load_env():
    """Load credentials from .env file."""
    env_path = PROJECT_DIR / ".env"
    if not env_path.exists():
        print(f"ERROR: {env_path} not found. Create it with TK_USER and TK_PASS.")
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

def download_csv(session: requests.Session, url: str, max_retries: int = 3) -> str | None:
    """
    Downloads a CSV from the given URL with retry logic.
    Returns the raw text content, or None if the file doesn't exist (404).
    """
    for attempt in range(1, max_retries + 1):
        try:
            resp = session.get(url, timeout=120)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.text
        except (requests.ConnectionError, requests.Timeout) as e:
            if attempt < max_retries:
                wait = 5 * attempt
                print(f"  ⚠ Connection error (attempt {attempt}/{max_retries}), retrying in {wait}s...")
                time.sleep(wait)
            else:
                print(f"  ✗ Failed after {max_retries} attempts: {e}")
                raise


def download_stations(session: requests.Session, base_url: str):
    """Download the latest stations metadata file."""
    STATIONS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = STATIONS_DIR / "latest-stations.parquet"

    if output_path.exists():
        print(f"✓ Stations file already exists: {output_path}")
        return

    # Use today's or yesterday's stations file
    for d in [date.today(), date.today() - timedelta(days=1), date.today() - timedelta(days=2)]:
        url = f"{base_url}/stations/{d.year}/{d.month:02d}/{d.strftime('%Y-%m-%d')}-stations.csv"
        print(f"  Trying stations file for {d}...")
        csv_text = download_csv(session, url)
        if csv_text:
            break
    else:
        print("  ✗ Could not find a recent stations file. Skipping.")
        return

    # Parse with Polars — stations CSV has messy quoting due to JSON column
    from io import StringIO
    df = pl.read_csv(
        StringIO(csv_text),
        infer_schema_length=10000,
        ignore_errors=True,
    )
    df.write_parquet(output_path, compression="zstd")
    print(f"✓ Stations saved: {output_path} ({df.height:,} stations, {output_path.stat().st_size / 1024:.0f} KB)")


def download_prices(session: requests.Session, base_url: str):
    """Download daily price files for the configured date range."""
    current = START_DATE
    end = END_DATE

    if TEST_MODE:
        end = min(START_DATE + timedelta(days=2), END_DATE)
        print(f"⚡ TEST MODE: downloading only {START_DATE} to {end}")

    total_days = (end - current).days + 1
    downloaded = 0
    skipped = 0
    failed = 0
    failed_dates = []
    last_successful_date = None

    print(f"\nDownloading prices: {current} → {end} ({total_days} days)")
    print("=" * 60)

    while current <= end:
        year_dir = PRICES_DIR / str(current.year)
        year_dir.mkdir(parents=True, exist_ok=True)
        output_path = year_dir / f"{current.strftime('%Y-%m-%d')}.parquet"

        day_num = (current - START_DATE).days + 1

        # Skip if already downloaded (idempotent!)
        # Crucial safety feature: always redownload/overwrite the last 2 days
        # to ensure we don't get incomplete partial days or lag-delayed prices!
        is_recent = current >= (end - timedelta(days=2))
        if output_path.exists() and not is_recent:
            skipped += 1
            last_successful_date = current
            current += timedelta(days=1)
            continue

        url = f"{base_url}/prices/{current.year}/{current.month:02d}/{current.strftime('%Y-%m-%d')}-prices.csv"
        progress = f"[{day_num}/{total_days}]"

        try:
            csv_text = download_csv(session, url)
            if csv_text is None:
                print(f"  {progress} {current} — 404 (no data)")
                failed += 1
                failed_dates.append(str(current))
                current += timedelta(days=1)
                continue

            # Parse CSV → Parquet in one shot
            from io import StringIO
            df = pl.read_csv(StringIO(csv_text), try_parse_dates=True)
            df.write_parquet(output_path, compression="zstd")

            size_kb = output_path.stat().st_size / 1024
            downloaded += 1
            last_successful_date = current
            print(f"  {progress} {current} — ✓ {df.height:,} rows, {size_kb:.0f} KB")

        except Exception as e:
            failed += 1
            failed_dates.append(str(current))
            print(f"  {progress} {current} — ✗ ERROR: {e}")

        current += timedelta(days=1)

    print("\n" + "=" * 60)
    print(f"Done! Downloaded: {downloaded}, Skipped (already had): {skipped}, Failed: {failed}")
    if failed_dates:
        print(f"Failed dates (No data available yet): {', '.join(failed_dates)}")

    today = date.today()
    if last_successful_date:
        delay_days = (today - last_successful_date).days
        print(f"\n📊 DATA FRESHNESS REPORT:")
        print(f"Current System Date:  {today}")
        print(f"Last Available Data:  {last_successful_date}")
        if delay_days == 0:
            print("Status: Up to date (No delay!)")
        else:
            print(f"Status: Data source is {delay_days} day(s) behind the current date.")
    else:
        print("No successful downloads found.")


# ==========================================
# 4. MAIN
# ==========================================

if __name__ == "__main__":
    user, password, base_url = load_env()

    # Create a persistent session with auth — reuses TCP connections for speed
    session = requests.Session()
    session.auth = (user, password)
    session.headers.update({"User-Agent": "TankAnalysis/1.0"})

    print(f"Tankerkönig Data Downloader")
    print(f"Target: {DATA_DIR}")
    print(f"Range:  {START_DATE} → {END_DATE}")
    if TEST_MODE:
        print("Mode:   ⚡ TEST (3 days only)")
    print()

    # Step 1: Stations metadata
    print("--- Downloading Stations Metadata ---")
    download_stations(session, base_url)

    # Step 2: Daily prices
    print("\n--- Downloading Daily Prices ---")
    download_prices(session, base_url)
