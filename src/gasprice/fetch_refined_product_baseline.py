"""
Module: fetch_refined_product_baseline.py
Description: Fetches full historical data (from 2005 to present) for Brent crude, 
             RBOB gasoline, Heating oil, and Ethanol futures, plus the EUR/USD rate.
             Performs unit conversions to EUR per liter and computes E5 and E10 
             blended wholesale product costs.
"""

import polars as pl
import logging
from datetime import datetime
from pathlib import Path

from gasprice.update_brent_crude import fetch_yahoo_data

# Setup paths and logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("gasprice.fetch_refined_product_baseline")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_FILE = DATA_DIR / "processed_refined_product_baseline.parquet"

BARREL_TO_LITER = 159.0
GALLON_TO_LITER = 3.785411784
GALLONS_PER_BARREL = 42.0

# The RB=F front month switches gasoline grade at the March (-> summer) and September (-> winter)
# contract rolls. German stations sell summer grade May 1 - Sep 30 (EU Directive 98/70/EC) and German
# pump prices followed the grade change only over these transition windows (2014-2025 data), so the
# RBOB grade jump is re-timed to them: full jump kept until the window opens, then phased out linearly.
SPRING_TRANSITION = ((3, 16), (4, 30))
AUTUMN_TRANSITION = ((10, 1), (11, 15))
# Share of the US grade jump that applies to German wholesale costs. Calibrated on 2015-2025 E5-vs-diesel
# spreads: the March jump carries over in full, while in September (German stations still on summer grade,
# so retailer pass-through cannot explain it) only about half of the US autumn drop is a German cost change.
SPRING_JUMP_SHARE = 1.0
AUTUMN_JUMP_SHARE = 0.5

def _transition_weight(roll_col: str, start: tuple[int, int], end: tuple[int, int]) -> pl.Expr:
    """Share of the grade jump still to be offset: 0 before the roll, 1 until the German
    transition window opens, then linearly down to 0 at its end."""
    start_d = pl.date(pl.col("_year"), *start)
    end_d = pl.date(pl.col("_year"), *end)
    ramp = (end_d - pl.col("date")).dt.total_days() / ((end_d - start_d).dt.total_days() + 1)
    return (
        pl.when(pl.col(roll_col).is_null() | (pl.col("date") < pl.col(roll_col)) | (pl.col("date") > end_d))
        .then(0.0)
        .when(pl.col("date") < start_d)
        .then(1.0)
        .otherwise(ramp)
    )


def align_gasoline_grade_to_germany(df: pl.DataFrame) -> pl.DataFrame:
    """Re-time the RBOB summer/winter grade switch to the German calendar.

    Expects daily rows with forward-filled `rbob_usd_gallon` and `brent_usd_barrel` and a boolean
    `rb_traded` marking days with an actual RB=F quote. The grade jump of each year is measured as the
    change in the RBOB-Brent crack on the first trading day of March and September and scaled by the
    German share. Adds
    `gasoline_grade_adj_usd_gallon` and returns `rbob_usd_gallon` with that adjustment applied.
    """
    traded = (
        df.filter(pl.col("rb_traded"))
        .sort("date")
        .with_columns((pl.col("rbob_usd_gallon") - pl.col("brent_usd_barrel") / GALLONS_PER_BARREL).alias("_crack"))
        .with_columns(
            pl.col("_crack").diff().alias("_jump"),
            pl.col("date").dt.year().alias("_year"),
            pl.col("date").dt.month().alias("_month"),
        )
    )
    rolls = (
        traded.filter(pl.col("_month").is_in([3, 9]))
        .group_by("_year", "_month")
        .agg(pl.col("date").min().alias("_roll"), pl.col("_jump").sort_by("date").first().alias("_jump"))
    )
    # Summer grade is dearer: keep only jumps in the expected direction (e.g. not the 2020 crash).
    spring = rolls.filter(pl.col("_month") == 3).select(
        "_year", pl.col("_roll").alias("_spring_roll"),
        (pl.col("_jump").clip(lower_bound=0.0) * SPRING_JUMP_SHARE).alias("_spring_jump"),
    )
    autumn = rolls.filter(pl.col("_month") == 9).select(
        "_year", pl.col("_roll").alias("_autumn_roll"),
        (pl.col("_jump").clip(upper_bound=0.0) * AUTUMN_JUMP_SHARE).alias("_autumn_jump"),
    )
    return (
        df.with_columns(pl.col("date").dt.year().alias("_year"))
        .join(spring, on="_year", how="left")
        .join(autumn, on="_year", how="left")
        .with_columns(
            (
                -pl.col("_spring_jump").fill_null(0.0) * _transition_weight("_spring_roll", *SPRING_TRANSITION)
                - pl.col("_autumn_jump").fill_null(0.0) * _transition_weight("_autumn_roll", *AUTUMN_TRANSITION)
            ).alias("gasoline_grade_adj_usd_gallon")
        )
        .with_columns((pl.col("rbob_usd_gallon") + pl.col("gasoline_grade_adj_usd_gallon")).alias("rbob_usd_gallon"))
        .drop("_year", "_spring_roll", "_spring_jump", "_autumn_roll", "_autumn_jump")
        .sort("date")
    )


def build_refined_product_baseline():
    # Fetch from 2005-01-01 to capture full historical trading of RBOB and Ethanol
    start_date = datetime(2005, 1, 1).date()
    end_date = datetime.today().date()
    
    logger.info(f"Downloading full history from {start_date} to {end_date}...")
    
    # Fetch all tickers
    logger.info("Fetching Brent crude (BZ=F)...")
    brent = fetch_yahoo_data("BZ=F", start_date, end_date).drop("partial").rename({"value": "brent_usd_barrel"})
    
    logger.info("Fetching RBOB gasoline (RB=F)...")
    rbob = fetch_yahoo_data("RB=F", start_date, end_date).drop("partial").rename({"value": "rbob_usd_gallon"})
    
    logger.info("Fetching Heating oil (HO=F)...")
    ho = fetch_yahoo_data("HO=F", start_date, end_date).drop("partial").rename({"value": "ho_usd_gallon"})
    
    logger.info("Fetching CBOT Ethanol (EH=F)...")
    ethanol = fetch_yahoo_data("EH=F", start_date, end_date).drop("partial").rename({"value": "ethanol_usd_gallon"})
    
    logger.info("Fetching EUR/USD rate (EURUSD=X)...")
    eurusd = fetch_yahoo_data("EURUSD=X", start_date, end_date).drop("partial").rename({"value": "eur_usd"})
    
    # Create master calendar date range
    logger.info("Merging and aligning calendar timelines...")
    calendar = pl.DataFrame({
        "date": pl.date_range(start_date, end_date, "1d", eager=True)
    })
    
    # Left join all data series
    merged = calendar.join(brent, on="date", how="left")
    merged = merged.join(rbob, on="date", how="left")
    merged = merged.join(ho, on="date", how="left")
    merged = merged.join(ethanol, on="date", how="left")
    merged = merged.join(eurusd, on="date", how="left")
    merged = merged.with_columns(pl.col("rbob_usd_gallon").is_not_null().alias("rb_traded"))
    
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
    
    logger.info("Re-timing the RBOB summer/winter grade switch to the German calendar...")
    merged = align_gasoline_grade_to_germany(merged)

    logger.info("Applying unit conversions and blend formulas...")
    # Convert individual elements to EUR per Liter
    converted = merged.with_columns([
        ((pl.col("brent_usd_barrel") / pl.col("eur_usd")) / BARREL_TO_LITER).alias("brent_eur_liter"),
        ((pl.col("rbob_usd_gallon") / pl.col("eur_usd")) / GALLON_TO_LITER).alias("gasoline_base_eur_liter"),
        ((pl.col("gasoline_grade_adj_usd_gallon") / pl.col("eur_usd")) / GALLON_TO_LITER).alias("gasoline_grade_adj_eur_liter"),
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
        "gasoline_grade_adj_eur_liter",
        "diesel_base_eur_liter",
        "ethanol_base_eur_liter",
        "e5_product_eur_liter",
        "e10_product_eur_liter",
        "diesel_product_eur_liter"
    ]).sort("date")
    
    # Defensive guard: ensure exactly one row per date
    final_df = final_df.unique("date", keep="last")
    
    # Write to parquet
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    final_df.write_parquet(OUTPUT_FILE, compression="zstd")
    
    logger.info("\n==========================================")
    logger.info("FINISHED BUILD SUCCESSFUL")
    logger.info("==========================================")
    logger.info(f"File:      {OUTPUT_FILE}")
    logger.info(f"Rows:      {final_df.height:,}")
    logger.info(f"Date range: {final_df['date'].min()} to {final_df['date'].max()}")
    logger.info(f"Sample E5 product cost:  €{final_df['e5_product_eur_liter'].tail(1)[0]:.4f}/L")
    logger.info(f"Sample E10 product cost: €{final_df['e10_product_eur_liter'].tail(1)[0]:.4f}/L")
    logger.info(f"Sample Diesel cost:      €{final_df['diesel_product_eur_liter'].tail(1)[0]:.4f}/L")

if __name__ == "__main__":
    build_refined_product_baseline()
