"""
Script: 08_build_dashboard_data.py
Description: Builds compact dashboard datasets from all local Tankerkoenig price data.

The raw daily files are price-change logs, not complete hourly snapshots. This
script therefore carries each station's last known price forward hour by hour.
That makes the intraday curve a station-level price estimate instead of an
average of price-change events.

Inputs:
    - ../data/tankerkoenig/prices/YYYY/YYYY-MM-DD.parquet
    - ../data/processed_macro_baseline.parquet
Outputs:
    - ../data/processed_daily_margins.parquet
    - ../data/processed_intraday.parquet
"""

import importlib.util
import sys
from pathlib import Path

import polars as pl

SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
DATA_DIR = PROJECT_DIR / "data"
PRICES_DIR = DATA_DIR / "tankerkoenig" / "prices"
MACRO_FILE = DATA_DIR / "processed_macro_baseline.parquet"
DAILY_OUTPUT_FILE = DATA_DIR / "processed_daily_margins.parquet"
INTRADAY_OUTPUT_FILE = DATA_DIR / "processed_intraday.parquet"

MIN_PRICE_VALID = 0.80
MAX_PRICE_VALID = 3.00
HOURS = pl.DataFrame({"hour": list(range(24))})

spec = importlib.util.spec_from_file_location(
    "tax_engine", str(SCRIPT_DIR / "02_tax_engine.py")
)
tax_engine = importlib.util.module_from_spec(spec)
sys.modules["tax_engine"] = tax_engine
spec.loader.exec_module(tax_engine)
calculate_net_price = tax_engine.calculate_net_price


def list_price_files() -> list[Path]:
    """Return all locally available daily price files in chronological order."""
    return sorted(PRICES_DIR.glob("*/*.parquet"))


def empty_station_state() -> pl.DataFrame:
    return pl.DataFrame(
        schema={
            "station_uuid": pl.String,
            "price_diesel": pl.Float64,
            "price_e5": pl.Float64,
            "price_e10": pl.Float64,
        }
    )


def valid_price(col_name: str) -> pl.Expr:
    return (
        pl.when((pl.col(col_name) > MIN_PRICE_VALID) & (pl.col(col_name) < MAX_PRICE_VALID))
        .then(pl.col(col_name))
        .otherwise(None)
    )


def read_hourly_changes(path: Path) -> pl.DataFrame:
    raw = (
        pl.read_parquet(path, columns=["date", "station_uuid", "diesel", "e5", "e10"])
        .with_columns(pl.col("date").dt.convert_time_zone("Europe/Berlin").alias("local_time"))
        .with_columns([
            pl.col("local_time").dt.date().alias("date"),
            pl.col("local_time").dt.hour().alias("hour"),
            valid_price("diesel").alias("price_diesel"),
            valid_price("e5").alias("price_e5"),
            valid_price("e10").alias("price_e10"),
        ])
        .sort(["station_uuid", "local_time"])
    )

    return (
        raw.group_by(["date", "hour", "station_uuid"])
        .agg([
            pl.col("price_diesel").drop_nulls().last(),
            pl.col("price_e5").drop_nulls().last(),
            pl.col("price_e10").drop_nulls().last(),
        ])
        .sort(["date", "station_uuid", "hour"])
    )


def build_hourly_snapshot(hourly_changes: pl.DataFrame, state: pl.DataFrame) -> pl.DataFrame:
    date_value = hourly_changes["date"].min()
    changed_stations = hourly_changes.select("station_uuid").unique()
    known_stations = state.select("station_uuid")

    stations = pl.concat([known_stations, changed_stations]).unique()
    grid = stations.join(HOURS, how="cross").with_columns(pl.lit(date_value).alias("date"))

    state_cols = {
        "price_diesel": "state_diesel",
        "price_e5": "state_e5",
        "price_e10": "state_e10",
    }
    state_for_join = state.rename(state_cols)

    return (
        grid.join(state_for_join, on="station_uuid", how="left")
        .join(hourly_changes, on=["date", "hour", "station_uuid"], how="left")
        .sort(["station_uuid", "hour"])
        .with_columns([
            pl.col("price_diesel").forward_fill().over("station_uuid").fill_null(pl.col("state_diesel")),
            pl.col("price_e5").forward_fill().over("station_uuid").fill_null(pl.col("state_e5")),
            pl.col("price_e10").forward_fill().over("station_uuid").fill_null(pl.col("state_e10")),
        ])
        .select(["date", "hour", "station_uuid", "price_diesel", "price_e5", "price_e10"])
    )


def summarize_hourly(snapshot: pl.DataFrame) -> pl.DataFrame:
    return (
        snapshot.group_by(["date", "hour"])
        .agg([
            pl.col("price_diesel").mean().alias("price_diesel"),
            pl.col("price_e5").mean().alias("price_e5"),
            pl.col("price_e10").mean().alias("price_e10"),
            pl.col("price_e5").count().alias("stations_reporting"),
        ])
        .sort(["date", "hour"])
    )


def summarize_daily(hourly_summary: pl.DataFrame) -> pl.DataFrame:
    return (
        hourly_summary.group_by("date")
        .agg([
            pl.col("price_diesel").mean().alias("price_diesel"),
            pl.col("price_e5").mean().alias("price_e5"),
            pl.col("price_e10").mean().alias("price_e10"),
            pl.col("stations_reporting").max().alias("stations_reporting"),
        ])
        .sort("date")
    )


def end_of_day_state(snapshot: pl.DataFrame) -> pl.DataFrame:
    return (
        snapshot.filter(pl.col("hour") == 23)
        .select(["station_uuid", "price_diesel", "price_e5", "price_e10"])
        .sort("station_uuid")
    )


def add_tax_and_spread_columns(df_daily: pl.DataFrame) -> pl.DataFrame:
    macro_df = pl.read_parquet(MACRO_FILE)
    df_joined = df_daily.join(
        macro_df.select(["date", "Raw_Material_EUR_per_Liter"]),
        on="date",
        how="left",
    ).with_columns(pl.col("Raw_Material_EUR_per_Liter").fill_null(strategy="forward"))

    def apply_and_rename(df: pl.DataFrame, price_col: str, fuel_type: str, prefix: str) -> pl.DataFrame:
        df_temp = calculate_net_price(df, "date", price_col, fuel_type)
        return (
            df_temp.with_columns([
                (pl.col("Price_Ex_VAT") * pl.col("VAT_Rate")).alias(f"{prefix}_vat"),
                pl.col("EBV_Tax").alias(f"{prefix}_ebv"),
                pl.col("CO2_Tax").alias(f"{prefix}_co2"),
                pl.col("Energy_Tax").alias(f"{prefix}_energy"),
                pl.col("Net_Product_Price").alias(f"{prefix}_net_price"),
            ])
            .drop(["VAT_Rate", "EBV_Tax", "CO2_Tax", "Energy_Tax", "Price_Ex_VAT", "Net_Product_Price"])
        )

    df_joined = apply_and_rename(df_joined, "price_e5", "petrol", "e5")
    df_joined = apply_and_rename(df_joined, "price_e10", "petrol", "e10")
    df_joined = apply_and_rename(df_joined, "price_diesel", "diesel", "diesel")

    return df_joined.with_columns([
        (pl.col("e5_net_price") - pl.col("Raw_Material_EUR_per_Liter")).alias("margin_e5"),
        (pl.col("e10_net_price") - pl.col("Raw_Material_EUR_per_Liter")).alias("margin_e10"),
        (pl.col("diesel_net_price") - pl.col("Raw_Material_EUR_per_Liter")).alias("margin_diesel"),
    ]).drop_nulls(subset=["price_e5", "Raw_Material_EUR_per_Liter"])


def run_pipeline() -> None:
    price_files = list_price_files()
    if not price_files:
        print(f"Error: no parquet files found under {PRICES_DIR}")
        return

    print("==========================================")
    print("BUILDING DASHBOARD DATASETS")
    print("==========================================")
    print(f"Input price archive: {PRICES_DIR}")
    print(f"Daily files: {len(price_files):,}")
    print("Method: station-level hourly snapshots with carry-forward state")

    state = empty_station_state()
    hourly_parts = []
    daily_parts = []

    for idx, path in enumerate(price_files, start=1):
        hourly_changes = read_hourly_changes(path)
        snapshot = build_hourly_snapshot(hourly_changes, state)
        hourly_summary = summarize_hourly(snapshot)

        hourly_parts.append(hourly_summary)
        daily_parts.append(summarize_daily(hourly_summary))
        state = end_of_day_state(snapshot)

        if idx % 100 == 0 or idx == len(price_files):
            latest_date = hourly_summary["date"].max()
            known_stations = state.height
            print(f"  processed {idx:,}/{len(price_files):,} files through {latest_date} ({known_stations:,} known stations)")

    intraday_df = pl.concat(hourly_parts, how="vertical").sort(["date", "hour"])
    daily_base_df = pl.concat(daily_parts, how="vertical").sort("date")
    daily_df = add_tax_and_spread_columns(daily_base_df)

    intraday_df.write_parquet(INTRADAY_OUTPUT_FILE, compression="zstd")
    daily_df.write_parquet(DAILY_OUTPUT_FILE, compression="zstd")

    print("\n==========================================")
    print("OUTPUT")
    print("==========================================")
    print(f"Intraday: {INTRADAY_OUTPUT_FILE} ({intraday_df.height:,} rows, {INTRADAY_OUTPUT_FILE.stat().st_size / 1024 / 1024:.2f} MB)")
    print(f"Daily:    {DAILY_OUTPUT_FILE} ({daily_df.height:,} rows, {DAILY_OUTPUT_FILE.stat().st_size / 1024:.0f} KB)")
    print(f"Date range: {daily_df['date'].min()} to {daily_df['date'].max()}")


if __name__ == "__main__":
    run_pipeline()
