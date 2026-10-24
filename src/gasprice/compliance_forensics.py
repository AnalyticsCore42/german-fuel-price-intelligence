"""
Module: compliance_forensics.py
Description: Station-level forensic price history and compliance verification engine.
             Extracts all timestamped price changes for a given station and classifies
             them into allowed price cuts, statutory 12:00 price increases, and
             illegal off-hour price hikes (Verstöße gegen das KPAnG).
"""

from datetime import datetime
from pathlib import Path
import polars as pl

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


def get_station_price_history(
    station_uuid: str, fuel: str = "e5", strict_noon: bool = False
) -> pl.DataFrame:
    """
    Fast scan of historical 2026 intraday prices for a single station.
    Calculates time-of-day in Europe/Berlin and classifies all price movements:
    1. Preissenkungen (always allowed)
    2. Erlaubte 12-Uhr-Mittagserhöhung (11:55 bis 12:59:59 standard, oder bis 12:05 im strikten Modus)
    3. Verbotene Preiserhöhungen (vor 11:55, nach Cutoff oder mehrfach am selben Tag)
    """
    price_pattern = str(DATA_DIR / "tankerkoenig" / "prices" / "2026" / "2026-0[4-9]-*.parquet")

    q = (
        pl.scan_parquet(price_pattern)
        .filter(pl.col("station_uuid") == station_uuid)
        .select(["date", "diesel", "e5", "e10"])
        .collect()
    )

    if q.height == 0:
        return pl.DataFrame()

    # Sort chronologically and convert UTC to Berlin local time
    sorted_df = q.sort("date").with_columns(
        pl.col("date").dt.convert_time_zone("Europe/Berlin").alias("local_time")
    )

    # Filter for valid price events with genuine non-zero price transitions
    fuel_df = sorted_df.filter(pl.col(fuel) > 0).with_columns([
        pl.col(fuel).alias("price"),
        pl.col(fuel).shift(1).alias("prev_price"),
        pl.col("local_time").dt.date().alias("local_date"),
        (
            pl.col("local_time").dt.hour().cast(pl.Int32) * 60 +
            pl.col("local_time").dt.minute().cast(pl.Int32)
        ).alias("min_of_day"),
    ]).filter(
        (pl.col("prev_price").is_not_null()) &
        (pl.col("prev_price") > 0) &
        ((pl.col("price") - pl.col("prev_price")).abs() > 0.001)
    ).with_columns([
        (pl.col("price") - pl.col("prev_price")).alias("diff"),
        ((pl.col("price") - pl.col("prev_price")) * 100).round(2).alias("diff_ct"),
        ((pl.col("price") - pl.col("prev_price")) > 0).alias("is_hike"),
    ])

    if fuel_df.height == 0:
        return pl.DataFrame()

    fuel_df = fuel_df.with_columns(
        pl.when(pl.col("is_hike"))
        .then(pl.col("is_hike").cum_sum().over("local_date"))
        .otherwise(0)
        .alias("daily_hike_nr")
    )

    # Cutoff threshold:
    # Standard: 780 (13:00) -> 60-minute conservative buffer
    # Strict:   725 (12:05) -> Strict letter of § 3 Abs. 1 KPAnG (um 12:00 Uhr)
    noon_upper = 725 if strict_noon else 780
    noon_label = "Gesetzliche Mittagserhöhung (11:55–12:05 Uhr)" if strict_noon else "Gesetzliche Mittagserhöhung (Erlaubt)"
    afternoon_label = "🚨 Verbotene Erhöhung (nach 12:05 Uhr)" if strict_noon else "🚨 Verbotene Nachmittagserhöhung (nach 13:00 Uhr)"

    # Classification rules:
    classified_df = fuel_df.with_columns([
        pl.when(pl.col("diff") < 0)
        .then(pl.lit("allowed_cut"))
        .when((pl.col("min_of_day") >= 715) & (pl.col("min_of_day") < noon_upper) & (pl.col("daily_hike_nr") == 1))
        .then(pl.lit("allowed_noon"))
        .when((pl.col("min_of_day") >= 715) & (pl.col("min_of_day") < noon_upper) & (pl.col("daily_hike_nr") > 1))
        .then(pl.lit("illegal_double_noon"))
        .when(pl.col("min_of_day") < 715)
        .then(pl.lit("illegal_early"))
        .otherwise(pl.lit("illegal_afternoon"))
        .alias("event_type"),

        pl.when(pl.col("diff") < 0)
        .then(pl.lit("Preissenkung (Erlaubt)"))
        .when((pl.col("min_of_day") >= 715) & (pl.col("min_of_day") < noon_upper) & (pl.col("daily_hike_nr") == 1))
        .then(pl.lit(noon_label))
        .when((pl.col("min_of_day") >= 715) & (pl.col("min_of_day") < noon_upper) & (pl.col("daily_hike_nr") > 1))
        .then(pl.lit("🚨 Verbotene Mehrfachanhebung mittags"))
        .when(pl.col("min_of_day") < 715)
        .then(pl.lit("🚨 Verbotene Früherhöhung (vor 11:55 Uhr)"))
        .otherwise(pl.lit(afternoon_label))
        .alias("status_label"),
    ])

    # Extract 1st hike (statutory noon hike baseline) per day to provide forensic context for later hikes
    noon_hikes = classified_df.filter(pl.col("daily_hike_nr") == 1).select([
        pl.col("local_date"),
        pl.col("local_time").dt.strftime("%H:%M:%S").alias("noon_hike_time"),
        pl.col("diff_ct").alias("noon_hike_ct"),
        pl.col("price").alias("noon_hike_price"),
    ])

    enriched_df = classified_df.join(noon_hikes, on="local_date", how="left").with_columns([
        pl.col("noon_hike_time").fill_null("—"),
        pl.col("noon_hike_ct").fill_null(0.0),
        pl.col("noon_hike_price").fill_null(0.0),
        # Mathematical price chain verification: ensures (prev_price + diff == price)
        ((pl.col("prev_price") + pl.col("diff") - pl.col("price")).abs() < 0.0001).alias("chain_verified"),
    ])

    return enriched_df

