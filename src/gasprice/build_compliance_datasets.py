"""
Build comprehensive compliance, lifecycle & multi-tolerance drift datasets for Kraftstoffpreisanpassungsgesetz:
1. Multi-tolerance precomputation:
   - standard_1300: Conservative forensic buffer (11:55–13:00 safe, hikes < 11:55 or >= 13:00 count)
   - buffer_1215: Technical transmission queue buffer (11:55–12:15 safe, hikes < 11:55 or >= 12:15 count)
   - strict_1205: Strict statutory letter of the law (11:55–12:05 safe, hikes < 11:55 or >= 12:05 count)
2. Station lifecycle forensics:
   - Tracks first_violation_date (min date) and last_violation_date (max date) per station.
   - Monthly violation breakdown (April onward) proving rollout timing (e.g. Esso's May bot deployment).
   - Categorizes lifecycle status (Spätstarter ab Mai, Dauersünder, Gestoppt, Einzelfall) and trajectory (Beschleunigend/Abflachend).
3. Lateness distribution:
   - Buckets all price hikes across the 24-hour day to show how many minutes late the violations are.
4. Outputs:
   - data/dashboard/compliance_daily_trend.parquet
   - data/dashboard/compliance_station_rankings.parquet
   - data/dashboard/compliance_lateness_distribution.parquet
"""
import os
from pathlib import Path

import polars as pl
from datetime import date

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PRICES_DIR = PROJECT_ROOT / "data" / "tankerkoenig" / "prices"
STATIONS_FILE = PROJECT_ROOT / "data" / "tankerkoenig" / "stations" / "cleaned-stations.parquet"
OUTPUT_DIR = PROJECT_ROOT / "data" / "dashboard"

# The 12:00 single-hike rule (KPAnG) applies from this date on.
RULE_START = date(2026, 4, 1)
MONTH_ABBR = {4: "apr", 5: "may", 6: "jun", 7: "jul", 8: "aug", 9: "sep", 10: "oct", 11: "nov", 12: "dec"}


def _rule_price_files() -> list[str]:
    """All daily price files from the rule start onward, across years."""
    files = []
    for fpath in PRICES_DIR.glob("*/*.parquet"):
        try:
            file_date = date.fromisoformat(fpath.stem)
        except ValueError:
            continue
        if file_date >= RULE_START:
            files.append(str(fpath))
    return sorted(files)


def build_compliance_data():
    price_files = _rule_price_files()
    print(f"Processing {len(price_files)} daily files from {os.path.basename(price_files[0])} to {os.path.basename(price_files[-1])}...")

    stations = pl.read_parquet(
        STATIONS_FILE,
        columns=["uuid", "brand", "street", "post_code", "city", "corporate_group", "region", "latitude", "longitude"]
    )
    
    last_prices = {}
    daily_trend_records = []
    station_day_violations = []

    # Aggregator for 24h hike lateness distribution
    lateness_bucket_counts = {
        "b1_morning": 0,       # < 11:55 (< 715)
        "b2_ontime": 0,        # 11:55 - 12:05 (715 - 725)
        "b3_lat15": 0,         # 12:05 - 12:15 (725 - 735)
        "b4_lat30": 0,         # 12:15 - 12:30 (735 - 750)
        "b5_lat60": 0,         # 12:30 - 13:00 (750 - 780)
        "b6_early_pm": 0,      # 13:00 - 15:00 (780 - 900)
        "b7_late_pm": 0,       # 15:00 - 18:00 (900 - 1080)
        "b8_evening": 0,       # 18:00 - 22:00 (1080 - 1320)
        "b9_night": 0,         # >= 22:00 (>= 1320)
    }

    for fpath in price_files:
        curr_date_str = os.path.basename(fpath).replace(".parquet", "")
        curr_date_obj = date.fromisoformat(curr_date_str)
        curr_month_int = curr_date_obj.month

        df = pl.read_parquet(
            fpath,
            columns=["date", "station_uuid", "diesel", "e5", "e10"]
        ).filter(
            (pl.col("diesel") > 0) | (pl.col("e5") > 0) | (pl.col("e10") > 0)
        ).sort(["station_uuid", "date"])

        # Convert to Europe/Berlin local time
        df = df.with_columns(
            pl.col("date").dt.convert_time_zone("Europe/Berlin").alias("local_time")
        )

        df = df.with_columns([
            (pl.col("diesel") - pl.col("diesel").shift(1).over("station_uuid")).alias("diesel_diff"),
            (pl.col("e5") - pl.col("e5").shift(1).over("station_uuid")).alias("e5_diff"),
            (pl.col("e10") - pl.col("e10").shift(1).over("station_uuid")).alias("e10_diff"),
            pl.int_range(0, pl.len()).over("station_uuid").alias("row_in_station")
        ])

        # Boundary checks against previous day
        first_rows = df.filter(pl.col("row_in_station") == 0).iter_rows(named=True)
        boundary_hikes = []
        for r in first_rows:
            uid = r["station_uuid"]
            if uid in last_prices:
                prev_d, prev_e5, prev_e10 = last_prices[uid]
                d_diff = r["diesel"] - prev_d if (r["diesel"] > 0 and prev_d > 0) else 0.0
                e5_diff = r["e5"] - prev_e5 if (r["e5"] > 0 and prev_e5 > 0) else 0.0
                e10_diff = r["e10"] - prev_e10 if (r["e10"] > 0 and prev_e10 > 0) else 0.0
                if d_diff > 0.001 or e5_diff > 0.001 or e10_diff > 0.001:
                    boundary_hikes.append({
                        "station_uuid": uid,
                        "local_time": r["local_time"],
                        "diesel_diff": d_diff,
                        "e5_diff": e5_diff,
                        "e10_diff": e10_diff
                    })

        # Save last prices of the day
        last_rows = df.group_by("station_uuid").last().iter_rows(named=True)
        for r in last_rows:
            last_prices[r["station_uuid"]] = (r["diesel"], r["e5"], r["e10"])

        # Intraday hikes
        intra_hikes = df.filter(
            (pl.col("row_in_station") > 0) &
            ((pl.col("diesel_diff") > 0.001) | (pl.col("e5_diff") > 0.001) | (pl.col("e10_diff") > 0.001))
        ).select(["station_uuid", "local_time", "diesel_diff", "e5_diff", "e10_diff"])

        if boundary_hikes:
            b_df = pl.DataFrame(boundary_hikes, schema=intra_hikes.schema)
            day_hikes = pl.concat([intra_hikes, b_df])
        else:
            day_hikes = intra_hikes

        active_stations_today = df["station_uuid"].n_unique()

        if len(day_hikes) == 0:
            continue

        # Extract minute of day in local time (cast to Int32 to prevent 8-bit integer overflow)
        day_hikes = day_hikes.with_columns([
            pl.col("local_time").dt.date().alias("date_local"),
            (pl.col("local_time").dt.hour().cast(pl.Int32) * 60 + pl.col("local_time").dt.minute().cast(pl.Int32)).alias("min_of_day")
        ])

        # Accumulate into lateness distribution buckets
        m_vals = day_hikes["min_of_day"].to_numpy()
        lateness_bucket_counts["b1_morning"] += int((m_vals < 715).sum())
        lateness_bucket_counts["b2_ontime"] += int(((m_vals >= 715) & (m_vals < 725)).sum())
        lateness_bucket_counts["b3_lat15"] += int(((m_vals >= 725) & (m_vals < 735)).sum())
        lateness_bucket_counts["b4_lat30"] += int(((m_vals >= 735) & (m_vals < 750)).sum())
        lateness_bucket_counts["b5_lat60"] += int(((m_vals >= 750) & (m_vals < 780)).sum())
        lateness_bucket_counts["b6_early_pm"] += int(((m_vals >= 780) & (m_vals < 900)).sum())
        lateness_bucket_counts["b7_late_pm"] += int(((m_vals >= 900) & (m_vals < 1080)).sum())
        lateness_bucket_counts["b8_evening"] += int(((m_vals >= 1080) & (m_vals < 1320)).sum())
        lateness_bucket_counts["b9_night"] += int((m_vals >= 1320).sum())

        # Classification across 3 tolerance levels:
        # Standard 13:00 (780)
        # Buffer 12:15 (735)
        # Strict 12:05 (725)
        day_hikes = day_hikes.with_columns([
            # Standard 13:00
            pl.when((pl.col("min_of_day") >= 715) & (pl.col("min_of_day") < 780))
            .then(pl.lit("safe"))
            .when(pl.col("min_of_day") < 715)
            .then(pl.lit("morning"))
            .otherwise(pl.lit("afternoon"))
            .alias("zone_1300"),
            # Buffer 12:15
            pl.when((pl.col("min_of_day") >= 715) & (pl.col("min_of_day") < 735))
            .then(pl.lit("safe"))
            .when(pl.col("min_of_day") < 715)
            .then(pl.lit("morning"))
            .otherwise(pl.lit("afternoon"))
            .alias("zone_1215"),
            # Strict 12:05
            pl.when((pl.col("min_of_day") >= 715) & (pl.col("min_of_day") < 725))
            .then(pl.lit("safe"))
            .when(pl.col("min_of_day") < 715)
            .then(pl.lit("morning"))
            .otherwise(pl.lit("afternoon"))
            .alias("zone_1205"),
        ])

        # Aggregate per station-day
        st_day = day_hikes.group_by("station_uuid").agg([
            pl.len().alias("total_hikes"),
            # 13:00
            (pl.col("zone_1300") == "safe").sum().alias("noon_hikes_1300"),
            (pl.col("zone_1300") == "morning").sum().alias("morning_hikes_1300"),
            (pl.col("zone_1300") == "afternoon").sum().alias("afternoon_hikes_1300"),
            (pl.col("zone_1300") != "safe").sum().alias("offhour_hikes_1300"),
            # 12:15
            (pl.col("zone_1215") == "safe").sum().alias("noon_hikes_1215"),
            (pl.col("zone_1215") != "safe").sum().alias("offhour_hikes_1215"),
            # 12:05
            (pl.col("zone_1205") == "safe").sum().alias("noon_hikes_1205"),
            (pl.col("zone_1205") != "safe").sum().alias("offhour_hikes_1205"),
            pl.max_horizontal(["diesel_diff", "e5_diff", "e10_diff"]).max().alias("max_hike_eur")
        ]).with_columns([
            # 1300 Intent & Offender
            (
                ((pl.col("noon_hikes_1300") > 0) & (pl.col("offhour_hikes_1300") > 0)) |
                (pl.col("offhour_hikes_1300") > 1)
            ).alias("is_intent_1300"),
            (
                (pl.col("noon_hikes_1300") == 0) & (pl.col("offhour_hikes_1300") == 1)
            ).alias("is_single_1300"),
            (pl.col("offhour_hikes_1300") > 0).alias("is_offender_1300"),

            # 1215 Intent & Offender
            (
                ((pl.col("noon_hikes_1215") > 0) & (pl.col("offhour_hikes_1215") > 0)) |
                (pl.col("offhour_hikes_1215") > 1)
            ).alias("is_intent_1215"),
            (
                (pl.col("noon_hikes_1215") == 0) & (pl.col("offhour_hikes_1215") == 1)
            ).alias("is_single_1215"),
            (pl.col("offhour_hikes_1215") > 0).alias("is_offender_1215"),

            # 1205 Intent & Offender
            (
                ((pl.col("noon_hikes_1205") > 0) & (pl.col("offhour_hikes_1205") > 0)) |
                (pl.col("offhour_hikes_1205") > 1)
            ).alias("is_intent_1205"),
            (
                (pl.col("noon_hikes_1205") == 0) & (pl.col("offhour_hikes_1205") == 1)
            ).alias("is_single_1205"),
            (pl.col("offhour_hikes_1205") > 0).alias("is_offender_1205"),
        ])

        # Daily trend entries for each tolerance
        for tol_key, is_off, is_int, is_sgl, morn_col, aft_col in [
            ("standard_1300", "is_offender_1300", "is_intent_1300", "is_single_1300", "morning_hikes_1300", "afternoon_hikes_1300"),
            ("buffer_1215", "is_offender_1215", "is_intent_1215", "is_single_1215", "morning_hikes_1300", "afternoon_hikes_1300"),
            ("strict_1205", "is_offender_1205", "is_intent_1205", "is_single_1205", "morning_hikes_1300", "afternoon_hikes_1300")
        ]:
            off_cnt = st_day.filter(pl.col(is_off)).height
            int_cnt = st_day.filter(pl.col(is_int)).height
            sgl_cnt = st_day.filter(pl.col(is_sgl)).height
            morn_cnt = st_day.filter(pl.col(morn_col) > 0).height
            aft_cnt = st_day.filter(pl.col(aft_col) > 0).height

            daily_trend_records.append({
                "date": curr_date_obj,
                "tolerance": tol_key,
                "active_stations": active_stations_today,
                "offending_stations": off_cnt,
                "offender_pct": (off_cnt / active_stations_today * 100) if active_stations_today > 0 else 0.0,
                "definite_intent_stations": int_cnt,
                "definite_intent_pct": (int_cnt / active_stations_today * 100) if active_stations_today > 0 else 0.0,
                "single_offhour_stations": sgl_cnt,
                "single_offhour_pct": (sgl_cnt / active_stations_today * 100) if active_stations_today > 0 else 0.0,
                "morning_violators": morn_cnt,
                "afternoon_violators": aft_cnt
            })

        # Keep station records that violated in any of the tolerances (or standard)
        violating_today = st_day.filter(
            pl.col("is_offender_1205") | pl.col("is_offender_1300")
        ).select([
            "station_uuid",
            "offhour_hikes_1300", "offhour_hikes_1215", "offhour_hikes_1205",
            "noon_hikes_1300", "morning_hikes_1300", "afternoon_hikes_1300",
            "is_intent_1300", "is_single_1300", "max_hike_eur"
        ]).with_columns([
            pl.lit(curr_date_obj).alias("date"),
            pl.lit(curr_month_int).alias("month")
        ])
        station_day_violations.append(violating_today)

    # 1. Compile Daily Trend DataFrame with Rolling Averages per Tolerance
    df_trend = pl.DataFrame(daily_trend_records).sort(["tolerance", "date"])
    df_trend = df_trend.with_columns([
        pl.col("offender_pct").rolling_mean(window_size=7, min_samples=1).over("tolerance").alias("offender_pct_7d_avg"),
        pl.col("definite_intent_pct").rolling_mean(window_size=7, min_samples=1).over("tolerance").alias("definite_intent_7d_avg")
    ])

    # 2. Compile Station Leaderboard with Forensic Lifecycle Tracking
    all_violations = pl.concat(station_day_violations)
    
    # Filter for standard 13:00 violations when computing core min/max dates and counts
    std_violations = all_violations.filter(pl.col("offhour_hikes_1300") > 0)

    data_end_date = date.fromisoformat(Path(price_files[-1]).stem)
    data_months = sorted({date.fromisoformat(Path(f).stem).month for f in price_files} | {4, 5, 6, 7, 8, 9})
    month_cols = [MONTH_ABBR[m] for m in data_months if m in MONTH_ABBR]

    station_lifecycle = std_violations.group_by("station_uuid").agg([
        pl.col("date").min().alias("first_violation_date"),
        pl.col("date").max().alias("last_violation_date"),
        *[(pl.col("month") == m).sum().alias(f"{MONTH_ABBR[m]}_violation_days") for m in data_months if m in MONTH_ABBR],
        *[
            pl.when(pl.col("month") == m).then(pl.col("offhour_hikes_1300")).otherwise(0).sum().alias(f"{MONTH_ABBR[m]}_hikes")
            for m in data_months if m in MONTH_ABBR
        ],
    ])

    station_rankings = all_violations.group_by("station_uuid").agg([
        # Standard 1300 counts
        (pl.col("offhour_hikes_1300") > 0).sum().alias("violation_days_count"),
        pl.col("offhour_hikes_1300").sum().alias("total_offhour_hikes"),
        pl.col("is_intent_1300").sum().alias("definite_intent_days"),
        pl.col("is_single_1300").sum().alias("single_offhour_days"),
        pl.col("morning_hikes_1300").sum().alias("morning_hikes_count"),
        pl.col("afternoon_hikes_1300").sum().alias("afternoon_hikes_count"),
        pl.col("max_hike_eur").max().alias("max_single_hike_eur"),
        # Buffer 1215 counts
        (pl.col("offhour_hikes_1215") > 0).sum().alias("violation_days_1215"),
        pl.col("offhour_hikes_1215").sum().alias("total_offhour_hikes_1215"),
        # Strict 1205 counts
        (pl.col("offhour_hikes_1205") > 0).sum().alias("violation_days_1205"),
        pl.col("offhour_hikes_1205").sum().alias("total_offhour_hikes_1205"),
    ]).join(station_lifecycle, on="station_uuid", how="left")

    station_rankings = station_rankings.join(
        stations, left_on="station_uuid", right_on="uuid", how="inner"
    ).with_columns([
        (pl.col("violation_days_count") / len(price_files) * 100).round(1).alias("violation_day_pct"),
        pl.col("post_code").str.slice(0, 2).alias("plz_2"),
        # Fill missing first/last date with overall date if zero 1300 hikes
        pl.col("first_violation_date").fill_null(RULE_START),
        pl.col("last_violation_date").fill_null(data_end_date),
        *[pl.col(f"{m}_hikes").fill_null(0) for m in month_cols],
    ]).with_columns([
        # Active span in calendar days
        ((pl.col("last_violation_date") - pl.col("first_violation_date")).dt.total_days() + 1).alias("active_days_span"),
        
        # Lifecycle Status Classification:
        pl.when(pl.col("violation_days_count") <= 2)
        .then(pl.lit("isolated"))            # Einzelfall (<= 2 Tage)
        .when(pl.col("last_violation_date") < date(2026, 8, 1))
        .then(pl.lit("stopped"))             # Gestoppt / Diszipliniert (vor August aufgehört)
        .when(pl.col("first_violation_date") >= date(2026, 5, 1))
        .then(pl.lit("late_starter"))        # Spätstarter ab Mai (z.B. Esso Bot-Rollout)
        .when((pl.col("first_violation_date") < date(2026, 5, 1)) & (pl.col("last_violation_date") >= date(2026, 9, 1)) & (pl.col("violation_days_count") >= 10))
        .then(pl.lit("persistent"))          # Dauersünder (von April bis September aktiv)
        .otherwise(pl.lit("sporadic"))
        .alias("lifecycle_status"),

        # Trajectory (Beschleunigend / Abflachend / Konstant)
        pl.when((pl.col("aug_hikes") + pl.col("sep_hikes") >= 1.5 * (pl.col("apr_hikes") + pl.col("may_hikes"))) & (pl.col("aug_hikes") + pl.col("sep_hikes") >= 4))
        .then(pl.lit("accelerating"))
        .when(pl.col("aug_hikes") + pl.col("sep_hikes") <= 0.5 * (pl.col("apr_hikes") + pl.col("may_hikes")))
        .then(pl.lit("decelerating"))
        .otherwise(pl.lit("constant"))
        .alias("trajectory")
    ]).sort("total_offhour_hikes", descending=True)

    # 3. Compile 24-Hour Lateness Distribution DataFrame
    total_lateness_hikes = sum(lateness_bucket_counts.values())
    lateness_records = [
        {"bucket_id": 1, "key": "b1_morning", "time_window": "< 11:55 Uhr", "label_de": "Vormittag (Vor 11:55 Uhr)", "label_en": "Morning (Before 11:55)", "count": lateness_bucket_counts["b1_morning"], "category": "illegal_morning"},
        {"bucket_id": 2, "key": "b2_ontime", "time_window": "11:55 – 12:05 Uhr", "label_de": "Pünktlich (11:55–12:05 Uhr)", "label_en": "On-Time (11:55–12:05)", "count": lateness_bucket_counts["b2_ontime"], "category": "legal_window"},
        {"bucket_id": 3, "key": "b3_lat15", "time_window": "12:05 – 12:15 Uhr", "label_de": "Server-Puffer (+5–15 Min.)", "label_en": "Server Buffer (+5–15 min)", "count": lateness_bucket_counts["b3_lat15"], "category": "buffer_latency"},
        {"bucket_id": 4, "key": "b4_lat30", "time_window": "12:15 – 12:30 Uhr", "label_de": "Leichte Verspätung (+15–30 Min.)", "label_en": "Slight Delay (+15–30 min)", "count": lateness_bucket_counts["b4_lat30"], "category": "slight_delay"},
        {"bucket_id": 5, "key": "b5_lat60", "time_window": "12:30 – 13:00 Uhr", "label_de": "Mittags-Drift (+30–60 Min.)", "label_en": "Midday Drift (+30–60 min)", "count": lateness_bucket_counts["b5_lat60"], "category": "midday_drift"},
        {"bucket_id": 6, "key": "b6_early_pm", "time_window": "13:00 – 15:00 Uhr", "label_de": "Früher Nachmittag (13:00–15:00 Uhr)", "label_en": "Early Afternoon (13:00–15:00)", "count": lateness_bucket_counts["b6_early_pm"], "category": "early_afternoon"},
        {"bucket_id": 7, "key": "b7_late_pm", "time_window": "15:00 – 18:00 Uhr", "label_de": "Nachmittag (15:00–18:00 Uhr)", "label_en": "Late Afternoon (15:00–18:00)", "count": lateness_bucket_counts["b7_late_pm"], "category": "afternoon"},
        {"bucket_id": 8, "key": "b8_evening", "time_window": "18:00 – 22:00 Uhr", "label_de": "Feierabend-Mitnahme (18:00–22:00 Uhr)", "label_en": "Evening Commute (18:00–22:00)", "count": lateness_bucket_counts["b8_evening"], "category": "commuter_wave"},
        {"bucket_id": 9, "key": "b9_night", "time_window": "≥ 22:00 Uhr", "label_de": "Nacht (Ab 22:00 Uhr)", "label_en": "Night (After 22:00)", "count": lateness_bucket_counts["b9_night"], "category": "night"},
    ]
    df_lateness = pl.DataFrame(lateness_records).with_columns([
        (pl.col("count") / total_lateness_hikes * 100).round(2).alias("share_pct")
    ])

    print("\n--- 24-HOUR HIKE LATENESS DISTRIBUTION ---")
    print(df_lateness)

    print("\n--- TOP 10 REPEAT OFFENDERS WITH FORENSIC LIFECYCLE ---")
    print(station_rankings.select([
        "brand", "street", "corporate_group", "city",
        "total_offhour_hikes", "violation_days_count",
        "first_violation_date", "last_violation_date",
        "lifecycle_status", "trajectory",
        "apr_hikes", "may_hikes", "jun_hikes", "sep_hikes"
    ]).head(10))

    # 4. Save to Parquet Files
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    df_trend.write_parquet(OUTPUT_DIR / "compliance_daily_trend.parquet")
    station_rankings.write_parquet(OUTPUT_DIR / "compliance_station_rankings.parquet")
    df_lateness.write_parquet(OUTPUT_DIR / "compliance_lateness_distribution.parquet")
    print("\nSuccessfully exported all 3 compliance datasets to data/dashboard/!")

if __name__ == "__main__":
    build_compliance_data()
