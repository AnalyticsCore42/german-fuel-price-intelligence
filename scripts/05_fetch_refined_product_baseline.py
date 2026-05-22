"""
Script: 05_fetch_refined_product_baseline.py
Description: Fetches full historical data (from 2005 to present) for Brent crude, 
             RBOB gasoline, Heating oil, and Ethanol futures, plus the EUR/USD rate.
             Performs unit conversions to EUR per liter and computes E5 and E10 
             blended wholesale product costs.
Outputs:
    - data/processed_refined_product_baseline.parquet
"""

import requests
import polars as pl
from datetime import datetime
from pathlib import Path

# Setup paths
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "data"
OUTPUT_FILE = DATA_DIR / "processed_refined_product_baseline.parquet"

BARREL_TO_LITER = 159.0
GALLON_TO_LITER = 3.785411784

def fetch_yahoo_data(ticker, start_date, end_date):
    start_ts = int(datetime.combine(start_date, datetime.min.time()).timestamp())
    end_ts = int(datetime.combine(end_date, datetime.min.time()).timestamp())
    
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?period1={start_ts}?2={end_ts}&period2={end_ts}&interval=1d"
    # Fallback to standard url without period1 query duplicate
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

def build_refined_product_baseline():
    # Fetch from 2005-01-01 to capture full historical trading of RBOB and Ethanol
    start_date = datetime(2005, 1, 1).date()
    end_date = datetime.today().date()
    
    print(f"Downloading full history from {start_date} to {end_date}...")
    
    # Fetch all tickers
    print("Fetching Brent crude (BZ=F)...")
    brent = fetch_yahoo_data("BZ=F", start_date, end_date).rename({"value": "brent_usd_barrel"})
    
    print("Fetching RBOB gasoline (RB=F)...")
    rbob = fetch_yahoo_data("RB=F", start_date, end_date).rename({"value": "rbob_usd_gallon"})
    
    print("Fetching Heating oil (HO=F)...")
    ho = fetch_yahoo_data("HO=F", start_date, end_date).rename({"value": "ho_usd_gallon"})
    
    print("Fetching CBOT Ethanol (EH=F)...")
    ethanol = fetch_yahoo_data("EH=F", start_date, end_date).rename({"value": "ethanol_usd_gallon"})
    
    print("Fetching EUR/USD rate (EURUSD=X)...")
    eurusd = fetch_yahoo_data("EURUSD=X", start_date, end_date).rename({"value": "eur_usd"})
    
    # Create master calendar date range
    print("Merging and aligning calendar timelines...")
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
    
    print("Applying unit conversions and blend formulas...")
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
    
    # Write to parquet
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    final_df.write_parquet(OUTPUT_FILE, compression="zstd")
    
    print("\n==========================================")
    print("FINISHED BUILD SUCCESSFUL")
    print("==========================================")
    print(f"File:      {OUTPUT_FILE}")
    print(f"Rows:      {final_df.height:,}")
    print(f"Date range: {final_df['date'].min()} to {final_df['date'].max()}")
    print(f"Sample E5 product cost:  €{final_df['e5_product_eur_liter'].tail(1)[0]:.4f}/L")
    print(f"Sample E10 product cost: €{final_df['e10_product_eur_liter'].tail(1)[0]:.4f}/L")
    print(f"Sample Diesel cost:      €{final_df['diesel_product_eur_liter'].tail(1)[0]:.4f}/L")

if __name__ == "__main__":
    build_refined_product_baseline()
