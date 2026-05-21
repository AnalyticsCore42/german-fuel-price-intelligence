#!/usr/bin/env python3
"""
Script: analyze_stations.py
Description: Analyze gas station data from Tankerkoenig with focus on brand names.
             Explores unique station names, brand distribution, and potential patterns.
"""

import polars as pl
from pathlib import Path

DATA_DIR = Path("/home/i/Music/1_Project_German_GasolinePrices/data")
STATIONS_FILE = DATA_DIR / "tankerkoenig" / "stations" / "latest-stations.parquet"

def main():
    print("Loading station data...")
    df = pl.read_parquet(STATIONS_FILE)
    print(f"Total stations: {df.shape[0]:,}")
    print(f"\nColumns: {df.columns}")

    # 1. Unique brands
    print("\n" + "="*50)
    print("1. BRAND ANALYSIS")
    print("="*50)

    brand_counts = df['brand'].value_counts()
    print(f"\nUnique brands: {df['brand'].n_unique()}")
    print(f"Stations with empty brand: {df['brand'].is_null().sum()}")

    print("\nTop 20 brands by station count:")
    print("-"*40)
    for row in brand_counts.head(20).iter_rows():
        brand, count = row
        brand_display = brand if brand else "(empty/None)"
        print(f"  {brand_display:<35} | {count:>5} stations")

    # 2. Unique station names
    print("\n" + "="*50)
    print("2. STATION NAME ANALYSIS")
    print("="*50)

    name_counts = df['name'].value_counts()
    print(f"\nUnique station names: {df['name'].n_unique()}")

    print("\nTop 20 station names by frequency:")
    print("-"*40)
    for row in name_counts.head(20).iter_rows():
        name, count = row
        print(f"  {name:<35} | {count:>5} stations")

    # 3. Brand vs Name - What patterns exist?
    print("\n" + "="*50)
    print("3. BRAND vs NAME PATTERNS")
    print("="*50)

    # Stations where brand matches part of name
    df_with_brand = df.filter(pl.col('brand').is_not_null() & (pl.col('brand') != ''))

    matching = []
    for row in df_with_brand.iter_rows():
        uuid, name, brand = row[0], row[1].lower(), row[2].lower()
        if brand in name:
            matching.append((name[:40], brand[:20]))

    print(f"\nStations where brand appears in station name: {len(matching)}")
    print("Examples:")
    for name, brand in matching[:10]:
        print(f"  Name: {name:<40} | Brand: {brand}")

    # 4. Analyze naming patterns
    print("\n" + "="*50)
    print("4. NAMING PATTERN ANALYSIS")
    print("="*50)

    # Common prefixes in station names
    print("\nCommon words/patterns in station names:")
    all_names = df['name'].to_list()
    all_names_lower = [n.lower() if n else "" for n in all_names if n]

    # Look for common terms
    common_terms = ['tankstelle', 'tanken', 'waschen', 'automat', 'strasse', 'straße']
    for term in common_terms:
        count = sum(1 for n in all_names_lower if term in n)
        print(f"  - '{term}': appears in {count} station names")

    # 5. Brand classification attempt
    print("\n" + "="*50)
    print("5. BRAND CLASSIFICATION")
    print("="*50)

    brand_list = df['brand'].unique().to_list()
    major_brands = []
    small_brands = []

    for brand in brand_list:
        if brand and len(brand) > 2:
            count = df.filter(pl.col('brand') == brand).shape[0]
            if count >= 5:
                major_brands.append((brand, count))
            else:
                small_brands.append((brand, count))

    major_brands.sort(key=lambda x: -x[1])
    small_brands.sort(key=lambda x: -x[1])

    print(f"\nMajor brands (5+ stations): {len(major_brands)}")
    print("-"*40)
    for brand, count in major_brands[:20]:
        print(f"  {brand:<30} | {count:>4} stations")

    print(f"\nSmall brands (<5 stations): {len(small_brands)}")
    print("First 10:")
    print("-"*40)
    for brand, count in small_brands[:10]:
        print(f"  {brand:<30} | {count:>4} stations")

    # 6. Geographic patterns by brand
    print("\n" + "="*50)
    print("6. GEOGRAPHIC PATTERNS BY BRAND")
    print("="*50)

    # Look at cities for major brands
    print("\nTop cities by station count:")
    city_counts = df['city'].value_counts().head(10)
    print("-"*40)
    for row in city_counts.iter_rows():
        city, count = row
        print(f"  {city:<25} | {count:>4} stations")

    # 7. Summary statistics
    print("\n" + "="*50)
    print("7. SUMMARY STATISTICS")
    print("="*50)
    print(f"\nTotal stations: {df.shape[0]:,}")
    print(f"Unique brands: {df['brand'].n_unique()}")
    print(f"Unique station names: {df['name'].n_unique()}")
    print(f"Unique cities: {df['city'].n_unique()}")

    # Date range
    if 'first_active' in df.columns:
        print(f"First active range: {df['first_active'].min()} to {df['first_active'].max()}")

if __name__ == "__main__":
    main()