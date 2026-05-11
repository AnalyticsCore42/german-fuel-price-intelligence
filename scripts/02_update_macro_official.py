"""
Script: 02_update_macro_official.py
Description: Updates the macroeconomic baseline using highly robust, official data sources
             (U.S. EIA for Brent Crude, European Central Bank for EUR/USD) to bypass 
             commercial API limitations and login walls.
Inputs:
    - ../data/processed_macro_baseline_1999_2026.parquet
Outputs:
    - Overwrites the parquet file with appended recent data.

Memory Constraint: Uses strictly Polars for processing to maintain <16GB footprint.
"""

import polars as pl
from datetime import datetime, timedelta
import os

# ==========================================
# 1. SETUP & CONFIGURATION
# ==========================================

PARQUET_FILE = "../data/processed_macro_baseline_1999_2026.parquet"
BARREL_TO_LITER = 159.0

# Official Data Endpoints
EIA_BRENT_URL = "https://www.eia.gov/dnav/pet/xls/PET_PRI_SPT_S1_D.xls"
ECB_EXR_BASE_URL = "https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A"

# ==========================================
# 2. DATA PIPELINE & POLARS PROCESSING
# ==========================================

def update_macro_data():
    if not os.path.exists(PARQUET_FILE):
        print(f"Error: {PARQUET_FILE} not found. Run 01_validate_macro_data.py first.")
        return
        
    print("Loading existing baseline data...")
    baseline_df = pl.read_parquet(PARQUET_FILE)
    
    max_date = baseline_df["date"].max()
    print(f"Existing data goes up to: {max_date}")
    
    start_fetch_date = max_date + timedelta(days=1)
    today = datetime.today().date()
    
    if start_fetch_date > today:
        print("Data is already fully up to date for today!")
        return
        
    start_str = start_fetch_date.strftime("%Y-%m-%d")
    print(f"Fetching official updates from {start_str} to today...")
    
    # ------------------------------------------
    # A. Fetch ECB Exchange Rates (EUR/USD)
    # ------------------------------------------
    ecb_url = f"{ECB_EXR_BASE_URL}?format=csvdata&startPeriod={start_str}"
    print("Downloading ECB Exchange Rates...")
    
    try:
        ecb_df = pl.read_csv(ecb_url)
        ecb_df = ecb_df.select([
            pl.col("TIME_PERIOD").str.strptime(pl.Date, "%Y-%m-%d").alias("date"),
            pl.col("OBS_VALUE").cast(pl.Float64).alias("DEXUSEU")
        ])
    except Exception as e:
        print(f"No new ECB data available or error: {e}")
        ecb_df = pl.DataFrame(schema={"date": pl.Date, "DEXUSEU": pl.Float64})
        
    # ------------------------------------------
    # B. Fetch EIA Brent Crude Spot Prices
    # ------------------------------------------
    print("Downloading EIA Brent Crude Spot Prices...")
    try:
        # Read the excel file using calamine engine
        eia_raw = pl.read_excel(EIA_BRENT_URL, sheet_name="Data 1", engine="calamine")
        
        # The actual data starts at row index 2
        # Column index 0 is Date, Column index 2 is Brent Crude
        eia_df = eia_raw.slice(2).select([
            pl.col(eia_raw.columns[0]).str.strptime(pl.Datetime, "%Y-%m-%d %H:%M:%S", strict=False).dt.date().alias("date"),
            pl.col(eia_raw.columns[2]).cast(pl.Float64, strict=False).alias("DCOILBRENTEU")
        ]).drop_nulls(subset=["date"])
        
        # Filter for only the new dates
        eia_df = eia_df.filter(pl.col("date") >= start_fetch_date)
    except Exception as e:
        print(f"Error fetching/parsing EIA data: {e}")
        eia_df = pl.DataFrame(schema={"date": pl.Date, "DCOILBRENTEU": pl.Float64})

    if ecb_df.is_empty() and eia_df.is_empty():
        print("No new trading data available yet from either source. Markets might be closed.")
        return
        
    # ------------------------------------------
    # C. Merge & Align Timelines
    # ------------------------------------------
    print("Aligning timelines and calculating raw material prices...")
    end_fetch_date = max(
        ecb_df["date"].max() if not ecb_df.is_empty() else start_fetch_date,
        eia_df["date"].max() if not eia_df.is_empty() else start_fetch_date
    )
    
    calendar_df = pl.DataFrame({
        "date": pl.date_range(start_fetch_date, end_fetch_date, "1d", eager=True)
    })
    
    new_merged_df = calendar_df.join(eia_df, on="date", how="left")
    new_merged_df = new_merged_df.join(ecb_df, on="date", how="left")
    
    # Forward fill missing weekend data
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
    # 3. MATH APPLICATION & FINALIZATION
    # ==========================================
    
    # Calculate the Raw Material Price
    new_merged_df = new_merged_df.with_columns(
        ((pl.col("DCOILBRENTEU") / pl.col("DEXUSEU")) / BARREL_TO_LITER)
        .alias("Raw_Material_EUR_per_Liter")
    )
    
    print("\n--- New Data Fetched ---")
    print(new_merged_df)
    
    # Append to baseline
    updated_baseline_df = pl.concat([baseline_df, new_merged_df])
    updated_baseline_df.write_parquet(PARQUET_FILE)
    
    print(f"\nSuccessfully appended {new_merged_df.height} new days to the baseline.")
    print(f"The baseline is now perfectly up to date through {updated_baseline_df['date'].max()}!")

if __name__ == "__main__":
    update_macro_data()
