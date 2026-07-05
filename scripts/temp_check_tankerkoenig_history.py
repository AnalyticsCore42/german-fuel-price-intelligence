"""
Temp script: probe the Tankerkönig historical-price repo backwards to find
how far back daily price CSVs are available via the configured credentials.
"""
from __future__ import annotations

import sys
import time
from datetime import date, timedelta
from pathlib import Path

import requests

# Make sure we can import the downloader's credential loader
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.gasprice.download_pump_prices import load_env  # noqa: E402


def build_url(base_url: str, d: date) -> str:
    return f"{base_url}/prices/{d.year}/{d.month:02d}/{d}-prices.csv"


def check_date(session: requests.Session, base_url: str, d: date) -> int | None:
    """Return HTTP status code, or None on error. Does not leak credentials."""
    url = build_url(base_url, d)
    try:
        resp = session.head(url, timeout=20)
        # Some Git hosts don't allow HEAD on raw files; fall back to a tiny GET.
        if resp.status_code == 405:
            resp = session.get(url, stream=True, timeout=20)
            resp.close()
        return resp.status_code
    except Exception as e:
        print(f"  network error for {d}: {e}")
        return None


def main() -> None:
    print("Loading credentials from .env ...")
    user, password, base_url = load_env()
    print(f"Base URL: {base_url}")
    print("Probing with authenticated HEAD/GET requests ...\n")

    session = requests.Session()
    session.auth = (user, password)

    # Sanity-check a known recent date first
    known = date(2021, 1, 1)
    status = check_date(session, base_url, known)
    print(f"  {known}: HTTP {status}")
    if status != 200:
        print("  WARNING: 2021-01-01 is not reachable; check credentials/base URL.")
        return

    # Coarse scan: first of every month backwards from 2021 to June 2014
    candidates = []
    y, m = 2021, 1
    while (y, m) >= (2014, 6):
        candidates.append(date(y, m, 1))
        y, m = (y, m - 1)
        if m == 0:
            y, m = y - 1, 12

    print("\nCoarse scan (1st of month):")
    earliest_month_with_data = None
    for d in candidates:
        status = check_date(session, base_url, d)
        exists = status == 200
        print(f"  {d}: HTTP {status} -> {'exists' if exists else 'missing'}")
        if exists:
            earliest_month_with_data = d
            # keep scanning to find the true earliest month
        time.sleep(0.2)

    if earliest_month_with_data is None:
        print("\nNo data found before 2021-01-01.")
        return

    print(f"\nEarliest month with a 1st-of-month file: {earliest_month_with_data}")

    # Fine scan within the earliest month to find the first actual day
    print(f"\nFine scan for first day of {earliest_month_with_data:%Y-%m}:")
    first_day = None
    current = earliest_month_with_data
    month_end = (current.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    while current <= month_end:
        status = check_date(session, base_url, current)
        exists = status == 200
        print(f"  {current}: HTTP {status} -> {'exists' if exists else 'missing'}")
        if exists:
            first_day = current
            break
        current += timedelta(days=1)
        time.sleep(0.2)

    if first_day:
        print(f"\n=> Earliest available daily price file: {first_day}")
    else:
        print(f"\n=> Could not pinpoint first day, but month {earliest_month_with_data:%Y-%m} has data.")


if __name__ == "__main__":
    main()
