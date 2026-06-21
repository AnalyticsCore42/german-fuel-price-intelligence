"""
Script: run_pipeline.py
Description: The central orchestrator that runs all stages of the Germany Gas Price 
             data preprocessing pipeline sequentially.
"""

import sys
from pathlib import Path

# Add src/ to sys.path so we can import the gasprice package
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from gasprice.clean_stations import clean_station_data
from gasprice.update_brent_crude import update_macro_data
from gasprice.fetch_refined_product_baseline import build_refined_product_baseline
from gasprice.build_dashboard_dataset import build_dashboard_datasets
from gasprice.station_price_stats import build_station_stats

def main():
    print("=" * 60)
    print("STARTING GAS PRICE ANALYSIS PIPELINE")
    print("=" * 60)
    
    # 1. Clean stations metadata
    print("\n[STEP 1/5] Cleaning station metadata...")
    stations_in = PROJECT_ROOT / "data" / "tankerkoenig" / "stations" / "latest-stations.parquet"
    stations_out = PROJECT_ROOT / "data" / "tankerkoenig" / "stations" / "cleaned-stations.parquet"
    clean_station_data(str(stations_in), str(stations_out))
    
    # 2. Update Brent crude macroeconomic baseline
    print("\n[STEP 2/5] Updating Brent Crude & Exchange Rates...")
    update_macro_data()
    
    # 3. Fetch refined product futures baseline
    print("\n[STEP 3/5] Fetching Refined Product Baselines...")
    build_refined_product_baseline()
    
    # 4. Build Streamlit dashboard dataset
    print("\n[STEP 4/5] Building Dashboard Datasets...")
    build_dashboard_datasets()
    
    # 5. Build station-level coordinates and rolling price stats
    print("\n[STEP 5/5] Building Station Price Stats (for Station Finder)...")
    build_station_stats()
    
    print("\n" + "=" * 60)
    print("PIPELINE EXECUTED SUCCESSFULLY")
    print("=" * 60)

if __name__ == "__main__":
    main()
