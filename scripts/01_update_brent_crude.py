"""
Script: 01_update_brent_crude.py
Description: Fetches the latest macroeconomic data (Brent Crude and EUR/USD) 
             from Yahoo Finance and updates the existing processed baseline parquet file.
Inputs:
    - ../data/processed_macro_baseline_1999_2026.parquet
Outputs:
    - Overwrites the parquet file with appended recent data.
"""

import polars as pl
import requests
import os
from datetime import datetime, timedelta
from pathlib import Path

# ==========================================
# 1. SETUP & CONFIGURATION
# ==========================================

SCRIPT_DIR = Path(__file__).parent
PARQUET_FILE = str(SCRIPT_DIR.parent / "data" / "processed_macro_baseline.parquet")
BARREL_TO_LITER = 159.0

# ==========================================
# 2. DATA PIPELINE & POLARS PROCESSING
# ==========================================

def fetch_yahoo_data(ticker, start_date, end_date):
    start_ts = int(datetime.combine(start_date, datetime.min.time()).timestamp())
    end_ts = int(datetime.combine(end_date, datetime.min.time()).timestamp())
    
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?period1={start_ts}&period2={end_ts}&interval=1d"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    res = requests.get(url, headers=headers).json()
    
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
    except Exception as e:
        print(f"Error parsing Yahoo data for {ticker}: {e}")
        return pl.DataFrame(schema={"date": pl.Date, "value": pl.Float64})

def update_macro_data():
    if not os.path.exists(PARQUET_FILE):
        print(f"Error: {PARQUET_FILE} not found. Run 01_validate_macro_data.py first.")
        return
        
    print("Loading existing baseline data...")
    baseline_df = pl.read_parquet(PARQUET_FILE)
    
    max_date = baseline_df["date"].max()
    print(f"Existing data goes up to: {max_date}")
    
    # Overwrite the last 5 days to account for weekends and lag/late reporting
    start_fetch_date = max_date - timedelta(days=5)
    end_fetch_date = datetime.today().date() + timedelta(days=1)
    
    start_str = start_fetch_date.strftime("%Y-%m-%d")
    end_str = end_fetch_date.strftime("%Y-%m-%d")
    print(f"Fetching updates from Yahoo Finance: {start_str} to {end_str}...")
    
    # Fetch data directly from Yahoo Finance JSON API
    brent_new = fetch_yahoo_data("BZ=F", start_fetch_date, end_fetch_date).rename({"value": "DCOILBRENTEU"})
    eurusd_new = fetch_yahoo_data("EURUSD=X", start_fetch_date, end_fetch_date).rename({"value": "DEXUSEU"})
    
    if brent_new.is_empty() or eurusd_new.is_empty():
        print("No new trading data available from Yahoo Finance yet. Markets might have been closed.")
        return
    
    # Align the new timelines on a daily basis
    calendar_df = pl.DataFrame({
        "date": pl.date_range(start_fetch_date, end_fetch_date - timedelta(days=1), "1d", eager=True)
    })
    
    new_merged_df = calendar_df.join(brent_new, on="date", how="left")
    new_merged_df = new_merged_df.join(eurusd_new, on="date", how="left")
    
    # Forward-fill missing weekend values
    new_merged_df = new_merged_df.with_columns([
        pl.col("DCOILBRENTEU").forward_fill(),
        pl.col("DEXUSEU").forward_fill()
    ])
    
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
    
    print("\n--- New Data Fetched (Yahoo Finance) ---")
    print(new_merged_df)
    
    # Filter old baseline to remove the days we are overwriting
    baseline_df = baseline_df.filter(pl.col("date") < start_fetch_date)
    
    # Append to baseline
    updated_baseline_df = pl.concat([baseline_df, new_merged_df]).sort("date")
    updated_baseline_df.write_parquet(PARQUET_FILE)
    
    print(f"\nSuccessfully appended/updated {new_merged_df.height} days in the baseline.")
    print(f"The baseline is now fully updated up to {updated_baseline_df['date'].max()}.")

if __name__ == "__main__":
    update_macro_data()
