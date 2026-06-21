"""
Script: 05_analyze_raw_data.py
Description: A quick diagnostic script to load the downloaded Tankerkönig data,
             inspect the schemas, and verify that the price data correctly maps
             to the station metadata.
"""

import polars as pl
from pathlib import Path

# ==========================================
# 1. SETUP
# ==========================================
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "data" / "tankerkoenig"
STATIONS_FILE = DATA_DIR / "stations" / "latest-stations.parquet"

# We'll just look at the very first day downloaded to test
PRICE_FILE = DATA_DIR / "prices" / "2021" / "2021-01-01.parquet"

def analyze():
    print("="*50)
    print("1. STATIONS DATA ANALYSIS")
    print("="*50)
    
    if not STATIONS_FILE.exists():
        print(f"ERROR: {STATIONS_FILE} not found.")
        return
        
    stations_df = pl.read_parquet(STATIONS_FILE)
    print(f"Total Stations: {stations_df.height:,}")
    print("\nColumns and Data Types:")
    for col, dtype in zip(stations_df.columns, stations_df.dtypes):
        print(f"  - {col}: {dtype}")
        
    print("\nSample Station:")
    print(stations_df.select(["uuid", "name", "brand", "city"]).head(3))
    
    print("\n" + "="*50)
    print("2. PRICE DATA ANALYSIS (2021-01-01)")
    print("="*50)
    
    if not PRICE_FILE.exists():
        print(f"ERROR: {PRICE_FILE} not found. Ensure the downloader has fetched Jan 1, 2021.")
        return
        
    prices_df = pl.read_parquet(PRICE_FILE)
    print(f"Total Price Changes on this day: {prices_df.height:,}")
    print("\nColumns and Data Types:")
    for col, dtype in zip(prices_df.columns, prices_df.dtypes):
        print(f"  - {col}: {dtype}")
        
    print("\nSample Price Changes:")
    print(prices_df.head(3))

    print("\n" + "="*50)
    print("3. DATA MAPPING VERIFICATION")
    print("="*50)
    
    # Check how many unique stations had price changes today
    unique_stations_with_prices = prices_df["station_uuid"].n_unique()
    print(f"Unique stations with price changes today: {unique_stations_with_prices:,}")
    
    # Check if the station_uuids in the price data exist in the master stations file
    # We do a left anti join: find rows in prices_df where station_uuid is NOT in stations_df
    unmapped_prices = prices_df.join(
        stations_df,
        left_on="station_uuid",
        right_on="uuid",
        how="anti"
    )
    
    unmapped_count = unmapped_prices.height
    print(f"Price change events missing a valid station UUID: {unmapped_count:,} ({(unmapped_count/prices_df.height)*100:.2f}%)")
    
    if unmapped_count == 0:
        print("\n[SUCCESS] 100% of the price data perfectly maps to our stations list!")
    else:
        print("\n[WARNING] Some price changes belong to stations that are no longer in the latest stations list.")
        print("This is normal for historical data (stations close down). We can easily filter these out.")

if __name__ == "__main__":
    analyze()
