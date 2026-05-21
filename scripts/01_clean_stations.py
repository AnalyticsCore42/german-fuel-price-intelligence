import polars as pl

def clean_station_data(input_path: str, output_path: str):
    print("Loading raw stations data...")
    df = pl.read_parquet(input_path)

    # 1. Clean the 'brand' column (Uppercase, strip whitespace, handle nulls/empty)
    df = df.with_columns(
        pl.col("brand")
        .fill_null("UNKNOWN")
        .str.strip_chars()
        .str.to_uppercase()
        .replace("", "UNKNOWN")
    )

    # 2. Define the Corporate Mapping (The verified Ground Truth!)
    # We map specific brands to their overarching corporate umbrellas.
    mapping = {
        "ARAL": "BP (Aral)",
        "SHELL": "Shell",
        "ESSO": "EG Group (Esso)",
        "TOTALENERGIES": "Couche-Tard (Total)",
        "TOTAL": "Couche-Tard (Total)",
        "ELAN": "Couche-Tard (Total)",
        "ACCESS": "Couche-Tard (Total)",
        "JET": "Stonepeak (JET)",
        "AGIP ENI": "Eni",
        "AGIP": "Eni",
        "STAR": "Orlen",
        "ORLEN": "Orlen",
        "WESTFALEN": "Westfalen AG",
        "MARKANT": "Westfalen AG",
        "HEM": "Oilinvest (HEM/Tamoil)",
        "T": "Oilinvest (HEM/Tamoil)",
        "OIL!": "Prax Group",
        "HOYER": "Hoyer Group",
        "SPRINT": "Hoyer Group",
        "SB": "SB (Generic/Discount)",
        "SUPERMARKT": "Grocery Retailers",
        "TANKCENTER": "Grocery Retailers"
    }

    # Create a Polars DataFrame from the mapping
    mapping_df = pl.DataFrame({
        "brand": list(mapping.keys()),
        "corporate_group": list(mapping.values())
    })

    # 3. Join the Corporate Group onto the main dataset
    # If a brand isn't in our mapping, it defaults to "Independent / Mittelstand"
    df_cleaned = df.join(mapping_df, on="brand", how="left").with_columns(
        pl.col("corporate_group").fill_null("Independent / Mittelstand")
    )

    # 4. Save the "Gold" dataset
    df_cleaned.write_parquet(output_path)
    print(f"✅ Cleaned dataset saved to {output_path}!")
    print("\nCorporate Group Distribution:")
    print(df_cleaned.group_by("corporate_group").len().sort("len", descending=True))

if __name__ == "__main__":
    clean_station_data(
        input_path="data/tankerkoenig/stations/latest-stations.parquet",
        output_path="data/tankerkoenig/stations/cleaned-stations.parquet"
    )
