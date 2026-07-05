"""
Module: build_dashboard_dataset.py
Description: Builds compact dashboard datasets from all local Tankerkoenig price data.
             Utilizes standard package imports and dynamic path resolutions.

Configuration:
    MAX_RAM_GB: Maximum RAM budget for the build step. Set to None for no limit
                (uses jemalloc, fast but ~12 GB peak). Set to a number (e.g. 4)
                to force system malloc and aggressive batch flushing (~25% slower
                but stays under the target).
"""

import gc
import os
import sys
from pathlib import Path
from queue import Queue
from threading import Thread
from datetime import date, timedelta
import json

# ==========================================
# MEMORY STRATEGY — set before Polars loads
# ==========================================
# Set to None for maximum speed (jemalloc, ~12 GB peak).
# Set to a GB value to cap memory at that level. 8 GB is a sensible default
# for most modern machines; reduce it if you run into memory pressure.
MAX_RAM_GB: int | None = 8

# A daily price file is considered complete if its latest observation is at or
# after this local hour (Europe/Berlin). The last file in an incremental run is
# skipped if incomplete, so partial days do not distort daily averages or the
# carry-forward state. The next run will reprocess it.
MIN_DAILY_HOUR_FOR_COMPLETE = 23

if MAX_RAM_GB is not None:
    # Force Polars to use glibc malloc instead of jemalloc.
    # System malloc returns freed pages to the OS via munmap(),
    # while jemalloc retains them in internal pools forever.
    os.environ["POLARS_FORCE_MALLOC"] = "1"

import polars as pl

from gasprice.tax_engine import calculate_net_price

# ==========================================
# 1. SETUP & CONFIGURATION
# ==========================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
PRICES_DIR = DATA_DIR / "tankerkoenig" / "prices"
MACRO_FILE = DATA_DIR / "processed_macro_baseline.parquet"
REFINED_BASE_FILE = DATA_DIR / "processed_refined_product_baseline.parquet"
STATIONS_FILE = DATA_DIR / "tankerkoenig" / "stations" / "cleaned-stations.parquet"
DAILY_OUTPUT_FILE = DATA_DIR / "processed_daily_margins.parquet"
INTRADAY_OUTPUT_FILE = DATA_DIR / "processed_intraday.parquet"
BRAND_DAILY_OUTPUT_FILE = DATA_DIR / "processed_brand_daily_margins.parquet"
REGIONAL_DAILY_OUTPUT_FILE = DATA_DIR / "processed_regional_daily_margins.parquet"
STATE_FILE = DATA_DIR / "station_carry_forward_state.parquet"

MIN_PRICE_VALID = 0.80
MAX_PRICE_VALID = 3.00
MIN_BRAND_STATIONS = 50
OTHER_BRAND_BUCKET = "Other brands (<50 stations)"
HOURS = pl.DataFrame({"hour": list(range(24))})

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

def empty_station_metadata() -> pl.DataFrame:
    return pl.DataFrame(
        schema={
            "station_uuid": pl.String,
            "brand": pl.String,
            "brand_group": pl.String,
            "corporate_group": pl.String,
            "region": pl.String,
            "brand_station_count": pl.UInt32,
        }
    )

def load_station_metadata() -> pl.DataFrame:
    """Load cleaned station metadata and create the visible-brand bucket."""
    if not STATIONS_FILE.exists():
        print(f"Warning: station metadata not found at {STATIONS_FILE}; brand output will be skipped.")
        return empty_station_metadata()

    stations = pl.read_parquet(STATIONS_FILE)
    uuid_col = "uuid" if "uuid" in stations.columns else "station_uuid"

    metadata = stations.select([
        pl.col(uuid_col).cast(pl.String).alias("station_uuid"),
        pl.col("brand")
        .fill_null("UNKNOWN")
        .str.strip_chars()
        .str.to_uppercase()
        .replace("", "UNKNOWN")
        .alias("brand"),
        pl.col("corporate_group")
        .fill_null("Independent / Small Operator")
        .alias("corporate_group"),
        pl.col("region")
        .fill_null("Unknown Region")
        .alias("region"),
    ])
    brand_counts = metadata.group_by("brand").agg(pl.len().alias("brand_station_count"))

    return (
        metadata.join(brand_counts, on="brand", how="left")
        .with_columns(
            pl.when(pl.col("brand_station_count") >= MIN_BRAND_STATIONS)
            .then(pl.col("brand"))
            .otherwise(pl.lit(OTHER_BRAND_BUCKET))
            .alias("brand_group")
        )
        .select(["station_uuid", "brand", "brand_group", "corporate_group", "region", "brand_station_count"])
    )

def valid_price(col_name: str) -> pl.Expr:
    return (
        pl.when((pl.col(col_name) > MIN_PRICE_VALID) & (pl.col(col_name) < MAX_PRICE_VALID))
        .then(pl.col(col_name))
        .otherwise(None)
    )

def read_hourly_changes(path: Path) -> pl.DataFrame:
    raw = (
        pl.read_parquet(path, columns=["date", "station_uuid", "diesel", "e5", "e10", "dieselchange", "e5change", "e10change"])
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

    # A station can have multiple price changes at the exact same timestamp
    # (duplicate rows from overlapping imports). Keep the last one per natural key.
    raw = raw.unique(subset=["local_time", "station_uuid"], keep="last")

    return (
        raw.group_by(["date", "hour", "station_uuid"])
        .agg([
            pl.col("price_diesel").drop_nulls().last(),
            pl.col("price_e5").drop_nulls().last(),
            pl.col("price_e10").drop_nulls().last(),
        ])
        .sort(["date", "station_uuid", "hour"])
    )

def compute_daily_price_changes(snapshot: pl.DataFrame) -> pl.DataFrame:
    """
    Count true price transitions per station per day from the hourly snapshot.

    The raw Tankerkoenig `*change` columns are unreliable for this because
    overlapping imports can report the same physical price change many times.
    Instead, we count how often a station's posted price differs from the
    previous hour in the forward-filled snapshot.
    """
    date_value = snapshot["date"].min()
    return (
        snapshot.sort(["station_uuid", "hour"])
        .group_by("station_uuid")
        .agg([
            (pl.col("price_diesel") != pl.col("price_diesel").shift(1))
            .fill_null(False)
            .sum()
            .cast(pl.UInt32)
            .alias("changes_diesel"),
            (pl.col("price_e5") != pl.col("price_e5").shift(1))
            .fill_null(False)
            .sum()
            .cast(pl.UInt32)
            .alias("changes_e5"),
            (pl.col("price_e10") != pl.col("price_e10").shift(1))
            .fill_null(False)
            .sum()
            .cast(pl.UInt32)
            .alias("changes_e10"),
        ])
        .with_columns(pl.lit(date_value).alias("date"))
        .select(["date", "station_uuid", "changes_diesel", "changes_e5", "changes_e10"])
    )

def build_hourly_snapshot(hourly_changes: pl.DataFrame, state: pl.DataFrame) -> pl.DataFrame:
    """
    Build a 24-hour price snapshot for the stations that reported on this day.

    We deliberately do **not** carry forward stations that did not report today,
    and we do not carry forward a fuel-specific price when the station reported
    no valid price for that fuel today. Keeping stale prices from closed stations
    or from fuels a station stopped selling would paste old values into current
    averages and distort the dashboard (e.g. €1.409/L E5 values in 2026).

    For fuels that do report today, hour 0 is seeded from the previous day's
    end-of-day state and forward-filled through the day.
    """
    date_value = hourly_changes["date"].min()
    stations = hourly_changes.select("station_uuid").unique()

    grid = stations.join(HOURS, how="cross").with_columns(pl.lit(date_value).alias("date"))

    # Per-station, per-fuel flag: did this station post a valid price for this
    # fuel at any hour today? Used to stop stale fuel-specific carry-forward.
    fuel_validity = hourly_changes.group_by("station_uuid").agg([
        pl.col("price_diesel").is_not_null().max().alias("has_diesel_today"),
        pl.col("price_e5").is_not_null().max().alias("has_e5_today"),
        pl.col("price_e10").is_not_null().max().alias("has_e10_today"),
    ])

    state_cols = {
        "price_diesel": "state_diesel",
        "price_e5": "state_e5",
        "price_e10": "state_e10",
    }
    state_for_join = state.rename(state_cols)

    def seed_at_hour_0(price_col: str, state_col: str, has_col: str) -> pl.Expr:
        return (
            pl.when((pl.col("hour") == 0) & pl.col(has_col))
            .then(pl.col(price_col).fill_null(pl.col(state_col)))
            .otherwise(pl.col(price_col))
        )

    return (
        grid.join(fuel_validity, on="station_uuid", how="left")
        .join(state_for_join, on="station_uuid", how="left")
        .join(hourly_changes, on=["date", "hour", "station_uuid"], how="left")
        .with_columns([
            seed_at_hour_0("price_diesel", "state_diesel", "has_diesel_today"),
            seed_at_hour_0("price_e5", "state_e5", "has_e5_today"),
            seed_at_hour_0("price_e10", "state_e10", "has_e10_today"),
        ])
        .sort(["station_uuid", "hour"])
        .with_columns([
            pl.col("price_diesel").forward_fill(),
            pl.col("price_e5").forward_fill(),
            pl.col("price_e10").forward_fill(),
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

def summarize_brand_daily(
    snapshot: pl.DataFrame,
    station_metadata: pl.DataFrame,
    daily_changes: pl.DataFrame | None = None,
) -> pl.DataFrame:
    if station_metadata.is_empty():
        return pl.DataFrame(
            schema={
                "date": pl.Date,
                "analysis_level": pl.String,
                "comparison_group": pl.String,
                "price_diesel": pl.Float64,
                "price_e5": pl.Float64,
                "price_e10": pl.Float64,
                "changes_diesel": pl.Float64,
                "changes_e5": pl.Float64,
                "changes_e10": pl.Float64,
                "stations_reporting": pl.UInt32,
                "station_count": pl.UInt32,
            }
        )

    enriched = (
        snapshot.join(station_metadata, on="station_uuid", how="left")
        .with_columns([
            pl.col("brand").fill_null("UNKNOWN"),
            pl.col("brand_group").fill_null(OTHER_BRAND_BUCKET),
            pl.col("corporate_group").fill_null("Independent / Small Operator"),
        ])
    )

    def summarize_dimension(group_col: str, analysis_level: str) -> pl.DataFrame:
        base = (
            enriched.group_by(["date", group_col])
            .agg([
                pl.col("price_diesel").mean().alias("price_diesel"),
                pl.col("price_e5").mean().alias("price_e5"),
                pl.col("price_e10").mean().alias("price_e10"),
                pl.col("station_uuid").filter(pl.col("price_e5").is_not_null()).n_unique().alias("stations_reporting"),
                pl.col("station_uuid").n_unique().alias("station_count"),
            ])
            .rename({group_col: "comparison_group"})
            .with_columns(pl.lit(analysis_level).alias("analysis_level"))
        )

        if daily_changes is not None and not daily_changes.is_empty():
            changes_enriched = (
                daily_changes.join(station_metadata, on="station_uuid", how="left")
                .with_columns([
                    pl.col("brand_group").fill_null(OTHER_BRAND_BUCKET),
                    pl.col("corporate_group").fill_null("Independent / Small Operator"),
                ])
            )
            # Mean of the 0/1 indicators = share of stations in the group that
            # changed their posted price at least once today.
            changes_agg = (
                changes_enriched.group_by(["date", group_col])
                .agg([
                    pl.col("changes_diesel").mean().alias("changes_diesel"),
                    pl.col("changes_e5").mean().alias("changes_e5"),
                    pl.col("changes_e10").mean().alias("changes_e10"),
                ])
                .rename({group_col: "comparison_group"})
            )
            base = base.join(changes_agg, on=["date", "comparison_group"], how="left")
        else:
            base = base.with_columns([
                pl.lit(None).cast(pl.Float64).alias("changes_diesel"),
                pl.lit(None).cast(pl.Float64).alias("changes_e5"),
                pl.lit(None).cast(pl.Float64).alias("changes_e10"),
            ])

        return base.select([
            "date",
            "analysis_level",
            "comparison_group",
            "price_diesel",
            "price_e5",
            "price_e10",
            "changes_diesel",
            "changes_e5",
            "changes_e10",
            "stations_reporting",
            "station_count",
        ])

    return pl.concat([
        summarize_dimension("brand_group", "brand"),
        summarize_dimension("corporate_group", "owner"),
    ], how="vertical")

def summarize_regional_daily(snapshot: pl.DataFrame, station_metadata: pl.DataFrame) -> pl.DataFrame:
    if station_metadata.is_empty():
        return pl.DataFrame(
            schema={
                "date": pl.Date,
                "region": pl.String,
                "price_diesel": pl.Float64,
                "price_e5": pl.Float64,
                "price_e10": pl.Float64,
                "stations_reporting": pl.UInt32,
                "station_count": pl.UInt32,
            }
        )

    enriched = (
        snapshot.join(station_metadata, on="station_uuid", how="left")
        .with_columns([
            pl.col("region").fill_null("Unknown Region"),
        ])
    )

    return (
        enriched.group_by(["date", "region"])
        .agg([
            pl.col("price_diesel").mean().alias("price_diesel"),
            pl.col("price_e5").mean().alias("price_e5"),
            pl.col("price_e10").mean().alias("price_e10"),
            pl.col("station_uuid").filter(pl.col("price_e5").is_not_null()).n_unique().alias("stations_reporting"),
            pl.col("station_uuid").n_unique().alias("station_count"),
        ])
        .sort(["date", "region"])
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

    if REFINED_BASE_FILE.exists():
        refined_df = pl.read_parquet(REFINED_BASE_FILE)
        refined_subset = refined_df.select([
            "date",
            "brent_eur_liter",
            "e5_product_eur_liter",
            "e10_product_eur_liter",
            "diesel_product_eur_liter"
        ])
        df_joined = df_joined.join(
            refined_subset,
            on="date",
            how="left"
        ).with_columns([
            pl.col("brent_eur_liter").fill_null(strategy="forward"),
            pl.col("e5_product_eur_liter").fill_null(strategy="forward"),
            pl.col("e10_product_eur_liter").fill_null(strategy="forward"),
            pl.col("diesel_product_eur_liter").fill_null(strategy="forward"),
        ])

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

    # Compute standard spreads over raw Brent
    df_joined = df_joined.with_columns([
        (pl.col("e5_net_price") - pl.col("Raw_Material_EUR_per_Liter")).alias("margin_e5"),
        (pl.col("e10_net_price") - pl.col("Raw_Material_EUR_per_Liter")).alias("margin_e10"),
        (pl.col("diesel_net_price") - pl.col("Raw_Material_EUR_per_Liter")).alias("margin_diesel"),
    ])

    # Compute refining and retail margins if refined baseline exists
    if "e5_product_eur_liter" in df_joined.columns:
        df_joined = df_joined.with_columns([
            (pl.col("e5_net_price") - pl.col("e5_product_eur_liter")).alias("retail_margin_e5"),
            (pl.col("e10_net_price") - pl.col("e10_product_eur_liter")).alias("retail_margin_e10"),
            (pl.col("diesel_net_price") - pl.col("diesel_product_eur_liter")).alias("retail_margin_diesel"),
            (pl.col("e5_product_eur_liter") - pl.col("Raw_Material_EUR_per_Liter")).alias("refining_spread_e5"),
            (pl.col("e10_product_eur_liter") - pl.col("Raw_Material_EUR_per_Liter")).alias("refining_spread_e10"),
            (pl.col("diesel_product_eur_liter") - pl.col("Raw_Material_EUR_per_Liter")).alias("refining_spread_diesel"),
        ])

    return df_joined.drop_nulls(subset=["price_e5", "Raw_Material_EUR_per_Liter"])

def _get_rss_mb() -> float:
    try:
        import psutil
        process = psutil.Process()
        return process.memory_info().rss / 1024 / 1024
    except ImportError:
        return 0.0


def _flush_batch(parts: list[pl.DataFrame], tmp_dir: Path, prefix: str, batch_num: int) -> Path:
    """Concat accumulated DataFrames, write to a temp parquet, and clear the list."""
    if not parts:
        return None
    combined = pl.concat(parts, how="vertical")
    parts.clear()
    tmp_path = tmp_dir / f"{prefix}_batch_{batch_num:04d}.parquet"
    combined.write_parquet(tmp_path, compression="zstd")
    del combined
    return tmp_path


def _run_quality_checks(
    daily_df: pl.DataFrame,
    intraday_df: pl.DataFrame,
    brand_daily_df: pl.DataFrame | None = None,
) -> list[str]:
    """Return a list of human-readable quality warnings."""
    warnings = []

    # 1. Date gaps in daily output
    dates = daily_df["date"].sort().to_list()
    if len(dates) >= 2:
        expected_dates = {dates[0] + timedelta(days=i) for i in range((dates[-1] - dates[0]).days + 1)}
        missing = sorted(expected_dates - set(dates))
        if missing:
            warnings.append(
                f"Missing {len(missing)} date(s) in daily output, e.g. {missing[:3]}"
            )

    # 2. Low station reporting hours
    if "stations_reporting" in intraday_df.columns and not intraday_df.is_empty():
        median_reporting = intraday_df["stations_reporting"].median()
        if median_reporting and median_reporting > 0:
            low_days = intraday_df.filter(pl.col("stations_reporting") < median_reporting * 0.5)
            if low_days.height > 0:
                warnings.append(
                    f"{low_days.height:,} intraday hour(s) with <50% of median "
                    f"reporting stations (median={median_reporting:,.0f})"
                )

    # 3. Price outliers
    for fuel in ["e5", "e10", "diesel"]:
        col = f"price_{fuel}"
        if col in daily_df.columns:
            bad = daily_df.filter(
                (pl.col(col) < MIN_PRICE_VALID) | (pl.col(col) > MAX_PRICE_VALID)
            ).height
            if bad:
                warnings.append(
                    f"{bad:,} daily {fuel} price(s) outside [{MIN_PRICE_VALID}, {MAX_PRICE_VALID}]"
                )

    # 4. Extreme single-day jumps (> 30 ct)
    for fuel in ["e5", "e10", "diesel"]:
        col = f"price_{fuel}"
        if col in daily_df.columns:
            jumps = (
                daily_df.with_columns((pl.col(col) - pl.col(col).shift(1)).abs().alias("delta"))
                .filter(pl.col("delta") > 0.30)
                .height
            )
            if jumps:
                warnings.append(f"{jumps:,} day(s) with {fuel} jump > 30 ct/L")

    # 5. Brand-level change frequency sanity
    if (
        brand_daily_df is not None
        and not brand_daily_df.is_empty()
        and "changes_e5" in brand_daily_df.columns
    ):
        high_change_days = brand_daily_df.filter(pl.col("changes_e5") > 20).height
        if high_change_days:
            warnings.append(
                f"{high_change_days:,} brand-day row(s) with >20 e5 price changes/day"
            )

    return warnings


def _validate_incremental_inputs(
    last_processed_date: date | None,
    price_files: list[Path],
) -> tuple[bool, str]:
    """Cheap pre-run validation: detect gaps/overlaps between existing and new data."""
    if last_processed_date is None or not price_files:
        return True, "No prior state to validate."

    expected_next = last_processed_date + timedelta(days=1)
    actual_next = date.fromisoformat(price_files[0].stem)

    if actual_next == expected_next:
        return True, f"Continuous: next expected file {expected_next} found."

    if actual_next < expected_next:
        return (
            False,
            f"Overlap detected: first new file {actual_next} is before expected {expected_next}. "
            "Use --rebuild to reprocess from scratch.",
        )

    return (
        False,
        f"Gap detected: expected next file {expected_next}, found {actual_next}. "
        "Use --rebuild to reprocess from scratch.",
    )


def _write_state_metadata(last_date: date, state: pl.DataFrame, metadata_path: Path) -> None:
    """Write lightweight metadata describing the carry-forward state."""
    metadata = {
        "last_date": str(last_date),
        "station_count": state.height,
    }
    metadata_path.write_text(json.dumps(metadata))


def _read_and_concat_batches(tmp_files: list[Path]) -> pl.DataFrame:
    """Read all batch parquet files and concat into one DataFrame."""
    if not tmp_files:
        return pl.DataFrame()
    frames = [pl.read_parquet(p) for p in tmp_files]
    result = pl.concat(frames, how="vertical")
    del frames
    # Clean up temp files
    for p in tmp_files:
        p.unlink(missing_ok=True)
    return result


def build_dashboard_datasets() -> None:
    price_files = list_price_files()
    if not price_files:
        print(f"Error: no parquet files found under {PRICES_DIR}")
        return

    # Check for force rebuild CLI option
    force_rebuild = "--rebuild" in sys.argv or "--force" in sys.argv

    # Check last processed date and load state if available
    last_processed_date = None
    state = None
    if not force_rebuild and DAILY_OUTPUT_FILE.exists() and STATE_FILE.exists():
        try:
            last_processed_date = pl.read_parquet(DAILY_OUTPUT_FILE, columns=["date"])["date"].max()
            state = pl.read_parquet(STATE_FILE)
            print(f"Incremental mode: detected last processed date {last_processed_date}")
        except Exception as e:
            print(f"Warning: Could not read incremental state or outputs ({e}). Rebuilding from scratch.")
            last_processed_date = None
            state = None

    # Filter price files chronologically
    if last_processed_date is not None:
        price_files = [p for p in price_files if date.fromisoformat(p.stem) > last_processed_date]

    # Validate incremental continuity before starting work
    valid, validation_msg = _validate_incremental_inputs(last_processed_date, price_files)
    if not valid:
        print(f"Error: {validation_msg}")
        return
    print(f"  Validation: {validation_msg}")

    if not price_files:
        print("==========================================")
        print("BUILDING DASHBOARD DATASETS (UP-TO-DATE)")
        print("==========================================")
        print("No new price files to process. Outputs are already up-to-date!")
        return

    # Determine batch size dynamically based on MAX_RAM_GB config
    batch_size = 200
    if MAX_RAM_GB is not None:
        batch_size = max(50, min(200, int(MAX_RAM_GB * 12.5)))

    print("==========================================")
    print("BUILDING DASHBOARD DATASETS")
    print("==========================================")
    print(f"Input price archive: {PRICES_DIR}")
    print(f"Files to process: {len(price_files):,}")
    print("Method: station-level hourly snapshots with carry-forward state")
    if MAX_RAM_GB is not None:
        print(f"Memory Strategy: Cap memory target to {MAX_RAM_GB} GB (Force System Malloc, batch_size={batch_size})")
    else:
        print(f"Memory Strategy: Max speed (Jemalloc, batch_size={batch_size})")
    print(f"Initial RSS: {_get_rss_mb():.0f} MB")

    # Temp directory for batch spill files
    tmp_dir = DATA_DIR / ".tmp_build"
    tmp_dir.mkdir(exist_ok=True)

    if state is None:
        state = empty_station_state()
    station_metadata = load_station_metadata()

    # Accumulate within each batch, flush to disk at batch boundaries
    hourly_parts: list[pl.DataFrame] = []
    daily_parts: list[pl.DataFrame] = []
    brand_daily_parts: list[pl.DataFrame] = []
    regional_daily_parts: list[pl.DataFrame] = []

    # Track temp files per output stream
    hourly_tmp_files: list[Path] = []
    daily_tmp_files: list[Path] = []
    brand_tmp_files: list[Path] = []
    regional_tmp_files: list[Path] = []

    # Start prefetcher thread
    prefetch_queue = Queue(maxsize=4)

    def prefetch_worker():
        for path in price_files:
            try:
                hourly_df = read_hourly_changes(path)
                prefetch_queue.put((path, hourly_df))
            except Exception as e:
                prefetch_queue.put((path, e))

    prefetch_thread = Thread(target=prefetch_worker, daemon=True)
    prefetch_thread.start()

    peak_rss_mb = 0.0
    batch_num = 0

    for idx in range(1, len(price_files) + 1):
        path, hourly_changes = prefetch_queue.get()
        if isinstance(hourly_changes, Exception):
            raise hourly_changes

        # Skip an incomplete last file; it will be reprocessed once the day is
        # fully collected. This prevents forward-filling stale 14:00 prices to
        # 23:00 and publishing a partial daily average as if it were complete.
        is_last_file = idx == len(price_files)
        max_hour = int(hourly_changes["hour"].max()) if not hourly_changes.is_empty() else -1
        if is_last_file and max_hour < MIN_DAILY_HOUR_FOR_COMPLETE:
            print(
                f"  skipping incomplete last file {path.stem} "
                f"(latest hour {max_hour}); will reprocess when complete"
            )
            continue

        snapshot = build_hourly_snapshot(hourly_changes, state)
        hourly_summary = summarize_hourly(snapshot)
        daily_changes = compute_daily_price_changes(snapshot)

        hourly_parts.append(hourly_summary)
        daily_parts.append(summarize_daily(hourly_summary))
        brand_daily = summarize_brand_daily(snapshot, station_metadata, daily_changes)
        if not brand_daily.is_empty():
            brand_daily_parts.append(brand_daily)

        regional_daily = summarize_regional_daily(snapshot, station_metadata)
        if not regional_daily.is_empty():
            regional_daily_parts.append(regional_daily)

        state = end_of_day_state(snapshot)
        del hourly_changes, snapshot, brand_daily, regional_daily, daily_changes

        # Flush accumulated DataFrames to disk at batch boundaries
        if idx % batch_size == 0:
            batch_num += 1
            p = _flush_batch(hourly_parts, tmp_dir, "hourly", batch_num)
            if p:
                hourly_tmp_files.append(p)
            p = _flush_batch(daily_parts, tmp_dir, "daily", batch_num)
            if p:
                daily_tmp_files.append(p)
            p = _flush_batch(brand_daily_parts, tmp_dir, "brand", batch_num)
            if p:
                brand_tmp_files.append(p)
            p = _flush_batch(regional_daily_parts, tmp_dir, "regional", batch_num)
            if p:
                regional_tmp_files.append(p)
            gc.collect()

        if idx % 100 == 0 or idx == len(price_files):
            current_rss = _get_rss_mb()
            peak_rss_mb = max(peak_rss_mb, current_rss)
            latest_date = hourly_summary["date"].max()
            known_stations = state.height
            print(f"  processed {idx:,}/{len(price_files):,} files through {latest_date} ({known_stations:,} known stations) | RSS: {current_rss:,.0f} MB (peak: {peak_rss_mb:,.0f} MB)")

        del hourly_summary

    # Flush any remaining data from the final partial batch
    if hourly_parts:
        batch_num += 1
        p = _flush_batch(hourly_parts, tmp_dir, "hourly", batch_num)
        if p:
            hourly_tmp_files.append(p)
        p = _flush_batch(daily_parts, tmp_dir, "daily", batch_num)
        if p:
            daily_tmp_files.append(p)
        p = _flush_batch(brand_daily_parts, tmp_dir, "brand", batch_num)
        if p:
            brand_tmp_files.append(p)
        p = _flush_batch(regional_daily_parts, tmp_dir, "regional", batch_num)
        if p:
            regional_tmp_files.append(p)
    gc.collect()

    print(f"\n  Batch processing complete. Merging {batch_num} batch files...")

    # Read back all batches and build final outputs
    intraday_df = _read_and_concat_batches(hourly_tmp_files).sort(["date", "hour"])
    daily_base_df = _read_and_concat_batches(daily_tmp_files).sort("date")
    daily_df = add_tax_and_spread_columns(daily_base_df)
    del daily_base_df

    brand_daily_df = None
    if brand_tmp_files:
        brand_daily_base_df = _read_and_concat_batches(brand_tmp_files).sort([
            "analysis_level", "comparison_group", "date"
        ])
        brand_daily_df = add_tax_and_spread_columns(brand_daily_base_df)
        del brand_daily_base_df

    regional_daily_df = None
    if regional_tmp_files:
        regional_daily_base_df = _read_and_concat_batches(regional_tmp_files).sort([
            "region", "date"
        ])
        regional_daily_df = add_tax_and_spread_columns(regional_daily_base_df)
        del regional_daily_base_df

    # Load existing historical data for incremental merge
    if last_processed_date is not None:
        print("  Merging newly processed summaries with existing historical data...")
        try:
            if INTRADAY_OUTPUT_FILE.exists():
                intraday_df = pl.concat([pl.read_parquet(INTRADAY_OUTPUT_FILE), intraday_df], how="vertical")
            if DAILY_OUTPUT_FILE.exists():
                daily_df = pl.concat([pl.read_parquet(DAILY_OUTPUT_FILE), daily_df], how="vertical")
            if BRAND_DAILY_OUTPUT_FILE.exists() and brand_daily_df is not None:
                brand_daily_df = pl.concat([pl.read_parquet(BRAND_DAILY_OUTPUT_FILE), brand_daily_df], how="vertical")
            if REGIONAL_DAILY_OUTPUT_FILE.exists() and regional_daily_df is not None:
                regional_daily_df = pl.concat([pl.read_parquet(REGIONAL_DAILY_OUTPUT_FILE), regional_daily_df], how="vertical")
        except Exception as e:
            print(f"Warning: Failed to load existing outputs for incremental merge: {e}. Writing from scratch.")

    # Deduplicate and sort
    intraday_df = intraday_df.unique(subset=["date", "hour"], keep="last").sort(["date", "hour"])
    daily_df = daily_df.unique(subset=["date"], keep="last").sort("date")
    if brand_daily_df is not None:
        brand_daily_df = brand_daily_df.unique(
            subset=["date", "analysis_level", "comparison_group"], keep="last"
        )
    if regional_daily_df is not None:
        regional_daily_df = regional_daily_df.unique(
            subset=["date", "region"], keep="last"
        )

    # Run quality checks
    quality_warnings = _run_quality_checks(daily_df, intraday_df, brand_daily_df)
    if quality_warnings:
        print("\n  Quality checks:")
        for warning in quality_warnings:
            print(f"    ⚠ {warning}")
    else:
        print("\n  Quality checks: OK")

    # Write final outputs to disk
    intraday_df.write_parquet(INTRADAY_OUTPUT_FILE, compression="zstd")
    daily_df.write_parquet(DAILY_OUTPUT_FILE, compression="zstd")
    if brand_daily_df is not None:
        brand_daily_df.write_parquet(BRAND_DAILY_OUTPUT_FILE, compression="zstd")
    if regional_daily_df is not None:
        regional_daily_df.write_parquet(REGIONAL_DAILY_OUTPUT_FILE, compression="zstd")

    # Save carry-forward state and lightweight metadata
    state.write_parquet(STATE_FILE, compression="zstd")
    _write_state_metadata(daily_df["date"].max(), state, STATE_FILE.with_suffix(".json"))

    # Clean up temp directory
    try:
        tmp_dir.rmdir()
    except Exception:
        pass

    print("\n==========================================")
    print("OUTPUT")
    print("==========================================")
    print(f"Intraday: {INTRADAY_OUTPUT_FILE} ({intraday_df.height:,} rows, {INTRADAY_OUTPUT_FILE.stat().st_size / 1024 / 1024:.2f} MB)")
    print(f"Daily:    {DAILY_OUTPUT_FILE} ({daily_df.height:,} rows, {DAILY_OUTPUT_FILE.stat().st_size / 1024:.0f} KB)")
    if brand_daily_df is not None:
        print(f"Brand:    {BRAND_DAILY_OUTPUT_FILE} ({brand_daily_df.height:,} rows, {BRAND_DAILY_OUTPUT_FILE.stat().st_size / 1024 / 1024:.2f} MB)")
    if regional_daily_df is not None:
        print(f"Regional: {REGIONAL_DAILY_OUTPUT_FILE} ({regional_daily_df.height:,} rows, {REGIONAL_DAILY_OUTPUT_FILE.stat().st_size / 1024 / 1024:.2f} MB)")
    print(f"Date range: {daily_df['date'].min()} to {daily_df['date'].max()}")
    print(f"Peak RSS: {peak_rss_mb:,.0f} MB")

if __name__ == "__main__":
    build_dashboard_datasets()
