"""
Script: validate_macro_data.py
Description: Validates, cleans, and merges the macroeconomic datasets (Brent Crude and EUR/USD).
"""

import polars as pl
from pathlib import Path

# ==========================================
# 1. SETUP & CONFIGURATION
# ==========================================

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent

BRENT_FILE = str(PROJECT_ROOT / "data" / "seed_bulk_baseline_brent_crude.csv")
EURUSD_FILE = str(PROJECT_ROOT / "data" / "seed_bulk_baseline_eur_usd.csv")
BARREL_TO_LITER = 159.0

# ==========================================
# 2. DATA PIPELINE & POLARS PROCESSING
# ==========================================

def load_and_clean_fred_data(filepath: str, value_col: str) -> pl.DataFrame:
    """
    Loads a FRED CSV dataset. FRED represents missing data as '.' (e.g., on holidays).
    This function converts those to nulls and casts the column to Float64.
    """
    df = pl.read_csv(filepath, null_values=".")
    
    # Ensure value column is float
    df = df.with_columns(pl.col(value_col).cast(pl.Float64))
    
    # Ensure date is parsed correctly
    df = df.with_columns(
        pl.col("observation_date").str.strptime(pl.Date, "%Y-%m-%d").alias("date")
    ).drop("observation_date")
    
    return df

def validate_macro_data():
    print("Loading datasets...")
    
    # Load data
    brent_df = load_and_clean_fred_data(BRENT_FILE, "DCOILBRENTEU")
    eurusd_df = load_and_clean_fred_data(EURUSD_FILE, "DEXUSEU")
    
    # We want a continuous daily timeline starting from the beginning of the EUR/USD rate
    start_date = pl.date(1999, 1, 4)
    end_date = min(brent_df["date"].max(), eurusd_df["date"].max())
    
    print(f"Aligning timelines from {start_date} to {end_date}...")
    
    # Create a full daily calendar sequence to ensure no gaps (like weekends)
    calendar_df = pl.DataFrame({
        "date": pl.date_range(start_date, end_date, "1d", eager=True)
    })
    
    # Left join onto the calendar to align the data perfectly
    merged_df = calendar_df.join(brent_df, on="date", how="left")
    merged_df = merged_df.join(eurusd_df, on="date", how="left")
    
    # Forward-fill missing values (e.g., weekends and holidays use the last known market close price)
    # Forward filling ensures that a Saturday fuel price calculation correctly uses Friday's oil price.
    merged_df = merged_df.with_columns([
        pl.col("DCOILBRENTEU").forward_fill(),
        pl.col("DEXUSEU").forward_fill()
    ])
    
    # ==========================================
    # 3. MATH APPLICATION & VALIDATION
    # ==========================================
    
    # Calculate the crucial Raw Material Price (EUR/Liter)
    # Formula: (Brent Price in USD / EUR_USD Exchange Rate) / 159
    merged_df = merged_df.with_columns(
        ((pl.col("DCOILBRENTEU") / pl.col("DEXUSEU")) / BARREL_TO_LITER)
        .alias("Raw_Material_EUR_per_Liter")
    )
    
    # Drop rows that still have nulls (e.g., the very first few days if they were holidays)
    merged_df = merged_df.drop_nulls()
    
    # Print out summary statistics to validate the values
    print("\n--- Data Validation Report ---")
    print(f"Total trading+weekend days analyzed: {merged_df.height:,}")
    print(f"Missing values after forward-fill: {sum(merged_df.null_count().row(0))}")
    
    print("\n--- Summary Statistics ---")
    summary = merged_df.select([
        pl.col("DCOILBRENTEU").min().alias("Brent_Min_USD"),
        pl.col("DCOILBRENTEU").max().alias("Brent_Max_USD"),
        pl.col("DCOILBRENTEU").mean().alias("Brent_Mean_USD"),
        
        pl.col("DEXUSEU").min().alias("EURUSD_Min"),
        pl.col("DEXUSEU").max().alias("EURUSD_Max"),
        pl.col("DEXUSEU").mean().alias("EURUSD_Mean"),
        
        pl.col("Raw_Material_EUR_per_Liter").min().alias("RawMat_Min_EUR_L"),
        pl.col("Raw_Material_EUR_per_Liter").max().alias("RawMat_Max_EUR_L"),
        pl.col("Raw_Material_EUR_per_Liter").mean().alias("RawMat_Mean_EUR_L")
    ])
    
    # Iterate and print cleanly
    for col in summary.columns:
        print(f"{col:<20}: {summary[col][0]:.4f}")
        
    print("\n--- Sample of Recent Data ---")
    print(merged_df.tail(5))
    
    # Save the cleaned and processed baseline dataset for later
    output_path = str(PROJECT_ROOT / "data" / "processed_macro_baseline.parquet")
    merged_df.write_parquet(output_path)
    print(f"\nSaved cleaned macroeconomic baseline to {output_path}")

if __name__ == "__main__":
    validate_macro_data()
