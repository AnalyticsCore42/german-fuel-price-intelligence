"""
Module: fetch_refined_product_baseline.py
Description: Fetches full historical data (from 2005 to present) for Brent crude, 
             RBOB gasoline, Heating oil, and Ethanol futures, plus the EUR/USD rate.
             Performs unit conversions to EUR per liter and computes E5 and E10 
             blended wholesale product costs.
"""

import requests
import polars as pl
from requests.exceptions import RequestException
import time
import logging
import json
from datetime import datetime
from pathlib import Path

# Setup paths and logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("gasprice.fetch_refined_product_baseline")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_FILE = DATA_DIR / "processed_refined_product_baseline.parquet"

BARREL_TO_LITER = 159.0
GALLON_TO_LITER = 3.785411784

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
        result = res['chart']['result'][0]
        timestamps = result['timestamp']
        closes = result['indicators']['quote'][0]['close']
        
        dates = [datetime.fromtimestamp(ts).date() for ts in timestamps]
        valid_data = [(d, c) for d, c in zip(dates, closes) if c is not None]
        if not valid_data:
            return pl.DataFrame(schema={"date": pl.Date, "value": pl.Float64})
            
        valid_dates, valid_closes = zip(*valid_data)
        return pl.DataFrame({
            "date": list(valid_dates),
            "value": list(valid_closes)
        })
    except (KeyError, TypeError, IndexError, json.JSONDecodeError) as e:
        logger.error(f"Malformed response format from Yahoo Finance for ticker {ticker}: {e}")
        raise e

def build_refined_product_baseline():
    # Fetch from 2005-01-01 to capture full historical trading of RBOB and Ethanol
    start_date = datetime(2005, 1, 1).date()
    end_date = datetime.today().date()
    
    logger.info(f"Downloading full history from {start_date} to {end_date}...")
    
    # Fetch all tickers
    logger.info("Fetching Brent crude (BZ=F)...")
    brent = fetch_yahoo_data("BZ=F", start_date, end_date).rename({"value": "brent_usd_barrel"})
    
    logger.info("Fetching RBOB gasoline (RB=F)...")
    rbob = fetch_yahoo_data("RB=F", start_date, end_date).rename({"value": "rbob_usd_gallon"})
    
    logger.info("Fetching Heating oil (HO=F)...")
    ho = fetch_yahoo_data("HO=F", start_date, end_date).rename({"value": "ho_usd_gallon"})
    
    logger.info("Fetching CBOT Ethanol (EH=F)...")
    ethanol = fetch_yahoo_data("EH=F", start_date, end_date).rename({"value": "ethanol_usd_gallon"})
    
    logger.info("Fetching EUR/USD rate (EURUSD=X)...")
    eurusd = fetch_yahoo_data("EURUSD=X", start_date, end_date).rename({"value": "eur_usd"})
    
    # Create master calendar date range
    logger.info("Merging and aligning calendar timelines...")
    calendar = pl.DataFrame({
        "date": pl.date_range(start_date, end_date, "1d", eager=True)
    })
    
    # Left join all data series
    merged = calendar.join(brent, on="date", how="left")
    merged = merged.join(rbob, on="date", how="left")
    merged = merged.join(ho, on="date", how="left")
    merged = merged.join(ethanol, on="date", how="left")
    merged = merged.join(eurusd, on="date", how="left")
    
    # Forward-fill gaps for weekends, then backward-fill any initial nulls
    merged = merged.with_columns([
        pl.col("brent_usd_barrel").forward_fill(),
        pl.col("rbob_usd_gallon").forward_fill(),
        pl.col("ho_usd_gallon").forward_fill(),
        pl.col("ethanol_usd_gallon").forward_fill(),
        pl.col("eur_usd").forward_fill()
    ]).with_columns([
        pl.col("brent_usd_barrel").backward_fill(),
        pl.col("rbob_usd_gallon").backward_fill(),
        pl.col("ho_usd_gallon").backward_fill(),
        pl.col("ethanol_usd_gallon").backward_fill(),
        pl.col("eur_usd").backward_fill()
    ])
    
    logger.info("Applying unit conversions and blend formulas...")
    # Convert individual elements to EUR per Liter
    converted = merged.with_columns([
        ((pl.col("brent_usd_barrel") / pl.col("eur_usd")) / BARREL_TO_LITER).alias("brent_eur_liter"),
        ((pl.col("rbob_usd_gallon") / pl.col("eur_usd")) / GALLON_TO_LITER).alias("gasoline_base_eur_liter"),
        ((pl.col("ho_usd_gallon") / pl.col("eur_usd")) / GALLON_TO_LITER).alias("diesel_base_eur_liter"),
        ((pl.col("ethanol_usd_gallon") / pl.col("eur_usd")) / GALLON_TO_LITER).alias("ethanol_base_eur_liter"),
    ])
    
    # Compute blended E5 and E10 refined costs
    # E5 = 95% Petrol (RBOB) + 5% Ethanol
    # E10 = 90% Petrol (RBOB) + 10% Ethanol
    # Diesel = 100% Heating Oil (HO) as standard proxy
    final_df = converted.with_columns([
        (0.95 * pl.col("gasoline_base_eur_liter") + 0.05 * pl.col("ethanol_base_eur_liter")).alias("e5_product_eur_liter"),
        (0.90 * pl.col("gasoline_base_eur_liter") + 0.10 * pl.col("ethanol_base_eur_liter")).alias("e10_product_eur_liter"),
        pl.col("diesel_base_eur_liter").alias("diesel_product_eur_liter"),
    ])
    
    # Clean up output table
    final_df = final_df.select([
        "date",
        "eur_usd",
        "brent_usd_barrel",
        "brent_eur_liter",
        "gasoline_base_eur_liter",
        "diesel_base_eur_liter",
        "ethanol_base_eur_liter",
        "e5_product_eur_liter",
        "e10_product_eur_liter",
        "diesel_product_eur_liter"
    ]).sort("date")
    
    # Defensive guard: ensure exactly one row per date
    final_df = final_df.unique("date", keep="last")
    
    # Write to parquet
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    final_df.write_parquet(OUTPUT_FILE, compression="zstd")
    
    logger.info("\n==========================================")
    logger.info("FINISHED BUILD SUCCESSFUL")
    logger.info("==========================================")
    logger.info(f"File:      {OUTPUT_FILE}")
    logger.info(f"Rows:      {final_df.height:,}")
    logger.info(f"Date range: {final_df['date'].min()} to {final_df['date'].max()}")
    logger.info(f"Sample E5 product cost:  €{final_df['e5_product_eur_liter'].tail(1)[0]:.4f}/L")
    logger.info(f"Sample E10 product cost: €{final_df['e10_product_eur_liter'].tail(1)[0]:.4f}/L")
    logger.info(f"Sample Diesel cost:      €{final_df['diesel_product_eur_liter'].tail(1)[0]:.4f}/L")

if __name__ == "__main__":
    build_refined_product_baseline()
