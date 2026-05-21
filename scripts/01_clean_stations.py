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

    # 2. The Comprehensive Corporate Mapping (The Verified Ground Truth)
    mapping = {
        # Tier 1: Big Oil & Global Conglomerates
        "ARAL": "BP (Aral)",
        "SHELL": "Shell",
        "TOTALENERGIES": "Couche-Tard (Total)",
        "TOTAL": "Couche-Tard (Total)",
        "ELAN": "Couche-Tard (Total)",
        "ACCESS": "Couche-Tard (Total)",
        "AGIP ENI": "Eni",
        "AGIP": "Eni",
        "STAR": "Orlen (Polish State)",
        "ORLEN": "Orlen (Polish State)",

        # Tier 2: Private Equity & Acquisitions
        "JET": "Stonepeak (JET)",
        "ESSO": "EG Group (Esso)",
        "OIL!": "Prax Group",

        # Tier 3: The "Mittelstand" Consolidations (Mid-Sized Independents)
        "HOYER": "Hoyer Group",
        "SPRINT": "Hoyer Group",
        "WESTFALEN": "Westfalen AG",
        "MARKANT": "Westfalen AG",
        "CLASSIC": "Christian Lühmann GmbH",
        "NORDOEL": "Lother GmbH",
        "Q1": "Q1 Energie AG",
        "TEAM": "team energie GmbH",
        "PM": "PM Pfennings",
        "SCORE": "SCORE GmbH",
        "ED": "Erich Doetsch (ED)",

        # Tier 4: International Niche Holdings
        "HEM": "Oilinvest (HEM/Tamoil)",
        "T": "Oilinvest (HEM/Tamoil)",
        "CALPAM": "Bolloré Group",
        "GULF": "Gulf / Independent",

        # Tier 5: Cooperatives & Associations
        "BFT (FREIE)": "BFT (Independent Assoc.)",
        "BFT": "BFT (Independent Assoc.)",
        "FREI": "BFT (Independent Assoc.)",
        "FREIE": "BFT (Independent Assoc.)",
        "AVIA": "AVIA Cooperative",
        "RAIFFEISEN": "Agricultural Co-ops (Raiffeisen/BayWa)",
        "BAYWA": "Agricultural Co-ops (Raiffeisen/BayWa)",

        # Tier 6: Generics & Supermarkets
        "SB": "SB (Generic/Discount)",
        "SUPERMARKT": "Grocery Retailers",
        "TANKCENTER": "Grocery Retailers",
        "UNKNOWN": "Unknown"
    }

    # Create a Polars DataFrame from the mapping
    mapping_df = pl.DataFrame({
        "brand": list(mapping.keys()),
        "corporate_group": list(mapping.values())
    })

    # 3. Join the Corporate Group onto the main dataset
    # If a brand isn't in our mapping, it truly belongs in the long-tail Independent bucket
    df_cleaned = df.join(mapping_df, on="brand", how="left").with_columns(
        pl.col("corporate_group").fill_null("Independent / Small Operator")
    )

    # 4. Save the "Gold" dataset
    df_cleaned.write_parquet(output_path)
    print(f"✅ Cleaned dataset saved to {output_path}!")
    
    # 5. Print the new distribution to verify the fix!
    print("\nCorporate Group Distribution:")
    distribution = df_cleaned.group_by("corporate_group").len().sort("len", descending=True)
    print(distribution)

if __name__ == "__main__":
    clean_station_data(
        input_path="data/tankerkoenig/stations/latest-stations.parquet",
        output_path="data/tankerkoenig/stations/cleaned-stations.parquet"
    )
