"""
Script: 07_station_price_stats.py
Description: Builds a compact station-level price statistics parquet for the
             Gas Station Finder dashboard tab. For each of the ~17k stations
             with valid WGS84 coordinates, computes:
               - 14-day rolling average prices (e5, e10, diesel)
               - Most recent observed price and date
               - Station metadata (name, brand, city, street, lat, lng)
Inputs:  data/tankerkoenig/prices/<year>/<date>.parquet
         data/tankerkoenig/stations/cleaned-stations.parquet
Outputs: data/station_price_stats.parquet (~18k rows, <2MB)
"""

import polars as pl
from pathlib import Path

# ==========================================
# 1. SETUP & CONFIGURATION
# ==========================================

PROJECT_DIR = Path(__file__).parent.parent
PRICES_DIR = PROJECT_DIR / "data" / "tankerkoenig" / "prices"
STATIONS_FILE = PROJECT_DIR / "data" / "tankerkoenig" / "stations" / "cleaned-stations.parquet"
OUTPUT_FILE = PROJECT_DIR / "data" / "station_price_stats.parquet"

LOOKBACK_DAYS = 14
MIN_PRICE = 0.80
MAX_PRICE = 3.00

# German WGS84 bounding box (filter garbage coordinates)
LAT_MIN, LAT_MAX = 47.0, 56.0
LNG_MIN, LNG_MAX = 5.0, 16.0


# ==========================================
# 2. DATA PIPELINE
# ==========================================

def list_price_files() -> list[Path]:
    return sorted(PRICES_DIR.rglob("*.parquet"))


def load_station_metadata() -> pl.DataFrame:
    stations = pl.read_parquet(STATIONS_FILE)
    uuid_col = "uuid" if "uuid" in stations.columns else "station_uuid"

    return (
        stations.select([
            pl.col(uuid_col).cast(pl.String).alias("station_uuid"),
            pl.col("name").fill_null("Unknown").alias("station_name"),
            pl.col("brand").fill_null("UNKNOWN").str.strip_chars().str.to_uppercase().alias("brand"),
            pl.col("city").fill_null("").alias("city"),
            pl.col("street").fill_null("").alias("street"),
            pl.col("house_number").fill_null("").alias("house_number"),
            pl.col("post_code").fill_null("").alias("post_code"),
            pl.col("latitude").alias("latitude"),
            pl.col("longitude").alias("longitude"),
        ])
        .filter(
            (pl.col("latitude") > LAT_MIN) & (pl.col("latitude") < LAT_MAX)
            & (pl.col("longitude") > LNG_MIN) & (pl.col("longitude") < LNG_MAX)
        )
    )


def build_station_stats() -> None:
    price_files = list_price_files()
    if not price_files:
        print(f"Error: no parquet files found under {PRICES_DIR}")
        return

    # Use only the last LOOKBACK_DAYS files
    recent_files = price_files[-LOOKBACK_DAYS:]
    print("==========================================")
    print("BUILDING STATION PRICE STATISTICS")
    print("==========================================")
    print(f"Using last {len(recent_files)} daily price files")
    print(f"Date range: {recent_files[0].stem} to {recent_files[-1].stem}")

    # Load and concatenate recent price data
    price_parts = []
    for path in recent_files:
        day_df = (
            pl.read_parquet(path, columns=["date", "station_uuid", "diesel", "e5", "e10"])
            .with_columns(pl.col("date").dt.convert_time_zone("Europe/Berlin").alias("local_time"))
            .with_columns(pl.col("local_time").dt.date().alias("price_date"))
            .select([
                pl.col("station_uuid").cast(pl.String),
                pl.col("price_date"),
                pl.col("diesel").alias("price_diesel"),
                pl.col("e5").alias("price_e5"),
                pl.col("e10").alias("price_e10"),
            ])
        )
        price_parts.append(day_df)

    prices = pl.concat(price_parts, how="vertical")
    print(f"  Raw price rows loaded: {prices.height:,}")

    # Filter valid prices
    prices = prices.with_columns([
        pl.when((pl.col("price_diesel") > MIN_PRICE) & (pl.col("price_diesel") < MAX_PRICE))
        .then(pl.col("price_diesel")).otherwise(None).alias("price_diesel"),
        pl.when((pl.col("price_e5") > MIN_PRICE) & (pl.col("price_e5") < MAX_PRICE))
        .then(pl.col("price_e5")).otherwise(None).alias("price_e5"),
        pl.when((pl.col("price_e10") > MIN_PRICE) & (pl.col("price_e10") < MAX_PRICE))
        .then(pl.col("price_e10")).otherwise(None).alias("price_e10"),
    ])

    # Compute station-level averages over the lookback window
    avg_stats = (
        prices.group_by("station_uuid")
        .agg([
            pl.col("price_diesel").mean().alias("avg_price_diesel"),
            pl.col("price_e5").mean().alias("avg_price_e5"),
            pl.col("price_e10").mean().alias("avg_price_e10"),
        ])
    )

    # Get the latest observed price per station (last row per station by date)
    latest_prices = (
        prices.sort(["station_uuid", "price_date"])
        .group_by("station_uuid")
        .agg([
            pl.col("price_diesel").drop_nulls().last().alias("latest_price_diesel"),
            pl.col("price_e5").drop_nulls().last().alias("latest_price_e5"),
            pl.col("price_e10").drop_nulls().last().alias("latest_price_e10"),
            pl.col("price_date").max().alias("latest_price_date"),
        ])
    )

    # Load station metadata
    stations = load_station_metadata()
    print(f"  Valid stations (WGS84): {stations.height:,}")

    # Join everything together
    result = (
        stations
        .join(avg_stats, on="station_uuid", how="left")
        .join(latest_prices, on="station_uuid", how="left")
    )

    # Drop stations with no price data at all
    result = result.filter(pl.col("avg_price_e5").is_not_null())

    result.write_parquet(OUTPUT_FILE, compression="zstd")

    print(f"\n==========================================")
    print(f"OUTPUT")
    print(f"==========================================")
    print(f"Stations with prices: {result.height:,}")
    print(f"Output: {OUTPUT_FILE} ({OUTPUT_FILE.stat().st_size / 1024:.0f} KB)")
    print(f"Columns: {result.columns}")


if __name__ == "__main__":
    build_station_stats()
