"""
Script: 02_update_macro_yahoo.py
Description: Fetches the latest missing macroeconomic data (Brent Crude and EUR/USD) 
             from Yahoo Finance and updates the existing processed baseline parquet file.
Inputs:
    - ../data/processed_macro_baseline_1999_2026.parquet
Outputs:
    - Overwrites the parquet file with appended recent data.

Memory Constraint: Uses strictly Polars for processing to maintain <16GB footprint.
"""

import polars as pl
import yfinance as yf
from datetime import datetime, timedelta
import os

# ==========================================
# 1. SETUP & CONFIGURATION
# ==========================================

PARQUET_FILE = "../data/processed_macro_baseline_1999_2026.parquet"
BARREL_TO_LITER = 159.0

# ==========================================
# 2. DATA PIPELINE & POLARS PROCESSING
# ==========================================

def update_macro_data():
    if not os.path.exists(PARQUET_FILE):
        print(f"Error: {PARQUET_FILE} not found. Run 01_validate_macro_data.py first.")
        return
        
    print("Loading existing baseline data...")
    # Read the existing baseline
    baseline_df = pl.read_parquet(PARQUET_FILE)
    
    # Find the last date we have data for
    max_date = baseline_df["date"].max()
    print(f"Existing data goes up to: {max_date}")
    
    # We want to fetch from the day after the max_date
    start_fetch_date = max_date + timedelta(days=1)
    end_fetch_date = datetime.today().date() + timedelta(days=1) # yfinance end is exclusive
    
    if start_fetch_date >= end_fetch_date:
        print("Data is already fully up to date for today!")
        return
        
    start_str = start_fetch_date.strftime("%Y-%m-%d")
    end_str = end_fetch_date.strftime("%Y-%m-%d")
    print(f"Fetching updates from Yahoo Finance: {start_str} to {end_str}...")
    
    # Fetch data from Yahoo Finance
    brent_yf = yf.download("BZ=F", start=start_str, end=end_str, progress=False)
    eurusd_yf = yf.download("EURUSD=X", start=start_str, end=end_str, progress=False)
    
    if brent_yf.empty or eurusd_yf.empty:
        print("No new trading data available from Yahoo Finance yet. Markets might have been closed.")
        return
        
    # Extract the 'Close' prices and convert to Polars DataFrames
    brent_new = pl.DataFrame({
        "date": [d.date() for d in brent_yf.index],
        "DCOILBRENTEU": brent_yf["Close"].squeeze().tolist()
    })
    
    eurusd_new = pl.DataFrame({
        "date": [d.date() for d in eurusd_yf.index],
        "DEXUSEU": eurusd_yf["Close"].squeeze().tolist()
    })
    
    # Align the new timelines on a daily basis (forward fill weekends)
    calendar_df = pl.DataFrame({
        "date": pl.date_range(start_fetch_date, end_fetch_date - timedelta(days=1), "1d", eager=True)
    })
    
    new_merged_df = calendar_df.join(brent_new, on="date", how="left")
    new_merged_df = new_merged_df.join(eurusd_new, on="date", how="left")
    
    # Forward-fill missing values
    new_merged_df = new_merged_df.with_columns([
        pl.col("DCOILBRENTEU").forward_fill(),
        pl.col("DEXUSEU").forward_fill()
    ])
    
    # In case the very first day is missing (e.g., weekend right after max_date),
    # we need the last known values from the baseline to fill it.
    last_brent = baseline_df["DCOILBRENTEU"][-1]
    last_eurusd = baseline_df["DEXUSEU"][-1]
    
    new_merged_df = new_merged_df.with_columns(
        pl.col("DCOILBRENTEU").fill_null(last_brent),
        pl.col("DEXUSEU").fill_null(last_eurusd)
    )
    
    # ==========================================
    # 3. MATH APPLICATION & MERGE
    # ==========================================
    
    # Calculate the Raw Material Price
    new_merged_df = new_merged_df.with_columns(
        ((pl.col("DCOILBRENTEU") / pl.col("DEXUSEU")) / BARREL_TO_LITER)
        .alias("Raw_Material_EUR_per_Liter")
    )
    
    print("\n--- New Data to Append ---")
    print(new_merged_df)
    
    # Concatenate the old baseline with the new data
    updated_baseline_df = pl.concat([baseline_df, new_merged_df])
    
    # Save back to parquet
    updated_baseline_df.write_parquet(PARQUET_FILE)
    print(f"\nSuccessfully appended {new_merged_df.height} new days to the baseline.")
    print(f"The baseline is now fully updated up to {updated_baseline_df['date'].max()}.")

if __name__ == "__main__":
    update_macro_data()
