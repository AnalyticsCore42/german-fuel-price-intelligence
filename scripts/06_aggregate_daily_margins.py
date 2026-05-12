"""
Script: 06_aggregate_daily_margins.py
Description: Aggregates the massive Tankerkönig raw price dataset into daily national averages.
             Filters out extreme outliers and missing data (0.0).
             Joins the macroeconomic baseline (Brent Crude) and applies the tax deduction
             engine to calculate True Corporate Margins for Diesel, Super E5, and Super E10.
             Outputs a highly compressed Parquet file for the dashboard.
"""

import polars as pl
from pathlib import Path
import sys

# Import our tax deduction engine
import importlib.util
spec = importlib.util.spec_from_file_location("tax_engine", str(Path(__file__).parent / "03_tax_deduction_engine.py"))
tax_engine = importlib.util.module_from_spec(spec)
sys.modules["tax_engine"] = tax_engine
spec.loader.exec_module(tax_engine)
calculate_net_price = tax_engine.calculate_net_price

# ==========================================
# 1. SETUP & CONFIGURATION
# ==========================================

SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
DATA_DIR = PROJECT_DIR / "data"

PRICES_GLOB = DATA_DIR / "tankerkoenig" / "prices" / "*" / "*.parquet"
MACRO_FILE = DATA_DIR / "processed_macro_baseline_1999_2026.parquet"
OUTPUT_FILE = DATA_DIR / "processed_daily_margins_2021_2026.parquet"

# Configurable outlier limits (in EUR)
MIN_PRICE_VALID = 0.80
MAX_PRICE_VALID = 3.00

def run_pipeline():
    print("==========================================")
    print("1. AGGREGATING RAW TANKERKÖNIG DATA")
    print("==========================================")
    
    # Use LazyFrames (scan_parquet) to handle millions of rows efficiently
    print(f"Scanning raw files: {PRICES_GLOB}")
    try:
        raw_prices = pl.scan_parquet(PRICES_GLOB)
    except Exception as e:
        print(f"Error reading parquet files (maybe none downloaded yet?): {e}")
        return

    # Extract just the Date part from the UTC Datetime
    df_daily = raw_prices.with_columns([
        pl.col("date").dt.date().alias("date")
    ])
    
    # Create valid price masks (excluding 0.0 and extreme outliers)
    diesel_valid = (pl.col("diesel") > MIN_PRICE_VALID) & (pl.col("diesel") < MAX_PRICE_VALID)
    e5_valid = (pl.col("e5") > MIN_PRICE_VALID) & (pl.col("e5") < MAX_PRICE_VALID)
    e10_valid = (pl.col("e10") > MIN_PRICE_VALID) & (pl.col("e10") < MAX_PRICE_VALID)
    
    # Calculate daily national averages
    df_agg = df_daily.group_by("date").agg([
        pl.col("diesel").filter(diesel_valid).mean().alias("price_diesel"),
        pl.col("e5").filter(e5_valid).mean().alias("price_e5"),
        pl.col("e10").filter(e10_valid).mean().alias("price_e10"),
        pl.col("station_uuid").n_unique().alias("stations_reporting")
    ]).sort("date").collect() # Trigger the execution graph
    
    print(f"✓ Aggregated {df_agg.height} days of data.")

    print("\n==========================================")
    print("2. JOINING MACRO BASELINE")
    print("==========================================")
    
    macro_df = pl.read_parquet(MACRO_FILE)
    
    # Left join so we keep all our Tankerkönig days. 
    df_joined = df_agg.join(macro_df.select(["date", "Raw_Material_EUR_per_Liter"]), on="date", how="left")
    df_joined = df_joined.with_columns(pl.col("Raw_Material_EUR_per_Liter").fill_null(strategy="forward"))
    
    print("✓ Macro data joined successfully.")

    print("\n==========================================")
    print("3. APPLYING TAX DEDUCTION ENGINE")
    print("==========================================")
    
    # Helper to apply the tax engine and retain absolute tax values
    def apply_and_rename(df, price_col, fuel_type, prefix):
        df_temp = calculate_net_price(df, "date", price_col, fuel_type)
        return df_temp.with_columns([
            (pl.col("Price_Ex_VAT") * pl.col("VAT_Rate")).alias(f"{prefix}_vat"),
            pl.col("EBV_Tax").alias(f"{prefix}_ebv"),
            pl.col("CO2_Tax").alias(f"{prefix}_co2"),
            pl.col("Energy_Tax").alias(f"{prefix}_energy"),
            pl.col("Net_Product_Price").alias(f"{prefix}_net_price")
        ]).drop(["VAT_Rate", "EBV_Tax", "CO2_Tax", "Energy_Tax", "Price_Ex_VAT", "Net_Product_Price"])

    # Apply tax engine for each fuel type
    df_joined = apply_and_rename(df_joined, "price_e5", "petrol", "e5")
    df_joined = apply_and_rename(df_joined, "price_e10", "petrol", "e10")
    df_joined = apply_and_rename(df_joined, "price_diesel", "diesel", "diesel")

    
    # Calculate True Corporate Margins (Net Price - Raw Material Cost)
    df_joined = df_joined.with_columns([
        (pl.col("e5_net_price") - pl.col("Raw_Material_EUR_per_Liter")).alias("margin_e5"),
        (pl.col("e10_net_price") - pl.col("Raw_Material_EUR_per_Liter")).alias("margin_e10"),
        (pl.col("diesel_net_price") - pl.col("Raw_Material_EUR_per_Liter")).alias("margin_diesel")
    ])

    print("\n==========================================")
    print("4. CORRELATION ANALYSIS")
    print("==========================================")
    
    # We drop nulls just for the correlation calculation
    corr_df = df_joined.drop_nulls()
    if corr_df.height > 10:
        # Calculate standard Pearson correlation
        corr_0 = corr_df.select(pl.corr("Raw_Material_EUR_per_Liter", "price_e5")).item()
        print(f"Brent vs Super E5 Correlation (0-day lag): {corr_0:.3f}")
        
        # Calculate 2-day lag correlation
        # If Brent goes up today, does pump price go up in 2 days?
        # We shift Brent forward by 2 days, so today's pump price aligns with Brent from 2 days ago.
        lagged_brent = corr_df.with_columns(pl.col("Raw_Material_EUR_per_Liter").shift(2))
        corr_2 = lagged_brent.drop_nulls().select(pl.corr("Raw_Material_EUR_per_Liter", "price_e5")).item()
        print(f"Brent vs Super E5 Correlation (2-day lag): {corr_2:.3f}")
    else:
        print("Not enough data to calculate meaningful correlations yet.")

    print("\n==========================================")
    print("5. SAVING OUTPUT")
    print("==========================================")
    
    # Ensure no old missing data ruins the dashboard
    df_joined = df_joined.drop_nulls(subset=["price_e5", "Raw_Material_EUR_per_Liter"])
    
    df_joined.write_parquet(OUTPUT_FILE, compression="zstd")
    size_kb = OUTPUT_FILE.stat().st_size / 1024
    
    print(f"✓ Saved fully aggregated dashboard dataset:")
    print(f"  Path: {OUTPUT_FILE}")
    print(f"  Rows: {df_joined.height}")
    print(f"  Size: {size_kb:.0f} KB")

if __name__ == "__main__":
    run_pipeline()
