"""
Module: update_brent_crude.py
Description: Fetches the latest macroeconomic data (Brent Crude and EUR/USD) 
             from Yahoo Finance and updates the existing processed baseline parquet file.
             Includes robust retry logic and error handling.
"""

import polars as pl
import requests
from requests.exceptions import RequestException
import os
import time
import logging
import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

# ==========================================
# 1. SETUP & CONFIGURATION
# ==========================================

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("gasprice.update_brent_crude")

# Resolve PARQUET_FILE relative to project root
PROJECT_ROOT = Path(__file__).resolve().parents[2]
PARQUET_FILE = str(PROJECT_ROOT / "data" / "processed_macro_baseline.parquet")
BARREL_TO_LITER = 159.0

# ==========================================
# 2. DATA PIPELINE & POLARS PROCESSING
# ==========================================

def fetch_with_retry(url, headers, max_retries=3, backoff_factor=2):
    """
    Perform requests.get with timeout and exponential backoff retry.
    Propagates request exceptions after exhaustion.
    """
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"Fetching URL (attempt {attempt}/{max_retries}): {url}")
            res = requests.get(url, headers=headers, timeout=15)
            res.raise_for_status()
            return res.json()
        except RequestException as e:
            logger.warning(f"Transient network error on attempt {attempt}: {e}")
            if attempt == max_retries:
                logger.error(f"Failed to fetch {url} after {max_retries} attempts.")
                raise e
            time.sleep(backoff_factor ** attempt)

def fetch_yahoo_data(ticker, start_date, end_date):
    """
    Fetch historical daily data for a given ticker from Yahoo Finance.
    """
    start_ts = int(datetime.combine(start_date, datetime.min.time()).timestamp())
    end_ts = int(datetime.combine(end_date, datetime.min.time()).timestamp())
    
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?period1={start_ts}&period2={end_ts}&interval=1d"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        res = fetch_with_retry(url, headers=headers)
    except RequestException as e:
        logger.error(f"Network failure fetching {ticker}: {e}")
        raise e
        
    try:
        return parse_daily_bars(res['chart']['result'][0])
    except (KeyError, TypeError, IndexError, json.JSONDecodeError) as e:
        logger.error(f"Malformed response format from Yahoo Finance for ticker {ticker}: {e}")
        raise e

def parse_daily_bars(result, now=None):
    """
    Daily (date, close, partial) rows from a Yahoo chart result, dated in the exchange time zone.
    partial = the session has not ended yet (bar dated today or later in exchange time): its close is the
    last trade so far, and after the evening reopen (Sunday included) it already holds next-session trades.
    """
    tz = ZoneInfo(result['meta'].get('exchangeTimezoneName') or "UTC")
    today = (now or datetime.now(tz)).astimezone(tz).date()
    closes = result['indicators']['quote'][0]['close']
    rows = [(datetime.fromtimestamp(ts, tz).date(), c) for ts, c in zip(result['timestamp'], closes) if c is not None]
    if not rows:
        return pl.DataFrame(schema={"date": pl.Date, "value": pl.Float64, "partial": pl.Boolean})
    dates, values = zip(*rows)
    return pl.DataFrame({"date": list(dates), "value": list(values), "partial": [d >= today for d in dates]})

def update_macro_data():
    if not os.path.exists(PARQUET_FILE):
        logger.error(f"Parquet baseline file {PARQUET_FILE} not found. Ensure macro baseline has been generated.")
        raise FileNotFoundError(f"{PARQUET_FILE} not found.")
        
    logger.info("Loading existing baseline data...")
    baseline_df = pl.read_parquet(PARQUET_FILE)
    
    max_date = baseline_df["date"].max()
    logger.info(f"Existing data goes up to: {max_date}")
    
    # Overwrite the last 5 days to account for weekends and lag/late reporting
    start_fetch_date = max_date - timedelta(days=5)
    end_fetch_date = datetime.today().date() + timedelta(days=1)
    
    start_str = start_fetch_date.strftime("%Y-%m-%d")
    end_str = end_fetch_date.strftime("%Y-%m-%d")
    logger.info(f"Fetching updates from Yahoo Finance: {start_str} to {end_str}...")
    
    # Fetch data directly from Yahoo Finance JSON API
    brent_new = fetch_yahoo_data("BZ=F", start_fetch_date, end_fetch_date).rename({"value": "DCOILBRENTEU", "partial": "_partial_brent"})
    eurusd_new = fetch_yahoo_data("EURUSD=X", start_fetch_date, end_fetch_date).rename({"value": "DEXUSEU", "partial": "_partial_fx"})
    
    if brent_new.is_empty() or eurusd_new.is_empty():
        logger.info("No new trading data available from Yahoo Finance yet. Markets might have been closed.")
        return
    
    # Align the new timelines on a daily basis
    calendar_df = pl.DataFrame({
        "date": pl.date_range(start_fetch_date, end_fetch_date - timedelta(days=1), "1d", eager=True)
    })
    
    new_merged_df = calendar_df.join(brent_new, on="date", how="left")
    new_merged_df = new_merged_df.join(eurusd_new, on="date", how="left")
    
    # Forward-fill missing weekend values (a day filled from a partial session stays partial)
    new_merged_df = new_merged_df.with_columns([
        pl.col("DCOILBRENTEU").forward_fill(),
        pl.col("DEXUSEU").forward_fill(),
        pl.col("_partial_brent").forward_fill(),
        pl.col("_partial_fx").forward_fill(),
    ])
    new_merged_df = new_merged_df.with_columns(
        (pl.col("_partial_brent").fill_null(False) | pl.col("_partial_fx").fill_null(False)).alias("partial_day")
    ).drop("_partial_brent", "_partial_fx")
    
    # Fill remaining nulls at the start using the previous valid values from the baseline
    for col in ["DCOILBRENTEU", "DEXUSEU"]:
        valid_vals = baseline_df.filter(pl.col("date") < start_fetch_date)[col].drop_nulls()
        if not valid_vals.is_empty():
            last_val = valid_vals[-1]
            new_merged_df = new_merged_df.with_columns(pl.col(col).fill_null(last_val))
    
    # ==========================================
    # 3. MATH APPLICATION & MERGE
    # ==========================================
    
    # Calculate the Raw Material Price in EUR per Liter
    new_merged_df = new_merged_df.with_columns(
        ((pl.col("DCOILBRENTEU") / pl.col("DEXUSEU")) / BARREL_TO_LITER)
        .alias("Raw_Material_EUR_per_Liter")
    )
    
    logger.info("\n--- New Data Fetched (Yahoo Finance) ---")
    logger.info(new_merged_df)
    
    # Filter old baseline to remove the days we are overwriting
    baseline_df = baseline_df.filter(pl.col("date") < start_fetch_date)
    
    # Append to baseline and ensure no duplicate dates (defensive guard)
    # diagonal: baselines written before partial_day existed lack the column
    updated_baseline_df = (
        pl.concat([baseline_df, new_merged_df], how="diagonal")
        .with_columns(pl.col("partial_day").fill_null(False))
        .sort("date").unique("date", keep="last")
    )
    updated_baseline_df.write_parquet(PARQUET_FILE)

    partial_days = new_merged_df.filter(pl.col("partial_day"))["date"].to_list()
    if partial_days:
        logger.info(f"Partial day (session still open, value not final): {partial_days}")
    logger.info(f"Successfully appended/updated {new_merged_df.height} days in the baseline.")
    logger.info(f"The baseline is now fully updated up to {updated_baseline_df['date'].max()}.")

if __name__ == "__main__":
    update_macro_data()
