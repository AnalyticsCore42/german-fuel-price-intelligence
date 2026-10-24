"""
High-performance compliance and lag-attribution analysis for Kraftstoffpreisanpassungsgesetz.
Analyzes 2026-04-01 to 2026-09-18.
Determines whether off-hour hikes are technical reporting delays or genuine violations,
and produces ranking datasets by Station, PLZ, Region, and Corporate Group.
"""
import glob
import os
import polars as pl

def analyze_compliance():
    price_files = sorted(glob.glob("data/tankerkoenig/prices/2026/2026-0[4-9]-*.parquet"))
    print(f"Analyzing {len(price_files)} days from {os.path.basename(price_files[0])} to {os.path.basename(price_files[-1])}...")

    stations = pl.read_parquet(
        "data/tankerkoenig/stations/cleaned-stations.parquet",
        columns=["uuid", "name", "brand", "street", "post_code", "city", "corporate_group", "region"]
    )
    station_dict = {
        row["uuid"]: row for row in stations.iter_rows(named=True)
    }

    # Track last prices across daily boundaries
    # uuid -> (diesel, e5, e10)
    last_prices = {}

    # Accumulator lists
    all_station_day_records = []
    minute_dist = [0] * (24 * 60) # 1440 minutes
    hourly_counts = [0] * 24

    for f_idx, fpath in enumerate(price_files):
        df = pl.read_parquet(
            fpath,
            columns=["date", "station_uuid", "diesel", "e5", "e10"]
        ).filter(
            (pl.col("diesel") > 0) | (pl.col("e5") > 0) | (pl.col("e10") > 0)
        ).sort(["station_uuid", "date"])

        # Convert to local time
        df = df.with_columns(
            pl.col("date").dt.convert_time_zone("Europe/Berlin").alias("local_time")
        )

        # Within-day diffs
        df = df.with_columns([
            (pl.col("diesel") - pl.col("diesel").shift(1).over("station_uuid")).alias("diesel_diff"),
            (pl.col("e5") - pl.col("e5").shift(1).over("station_uuid")).alias("e5_diff"),
            (pl.col("e10") - pl.col("e10").shift(1).over("station_uuid")).alias("e10_diff"),
            pl.int_range(0, pl.len()).over("station_uuid").alias("row_in_station")
        ])

        # For row_in_station == 0, check against last_prices from previous day
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

        # Update last prices with the last record of each station in this file
        last_rows = df.group_by("station_uuid").last().iter_rows(named=True)
        for r in last_rows:
            last_prices[r["station_uuid"]] = (r["diesel"], r["e5"], r["e10"])

        # Intraday hikes (row_in_station > 0)
        intra_hikes = df.filter(
            (pl.col("row_in_station") > 0) &
            ((pl.col("diesel_diff") > 0.001) | (pl.col("e5_diff") > 0.001) | (pl.col("e10_diff") > 0.001))
        ).select(["station_uuid", "local_time", "diesel_diff", "e5_diff", "e10_diff"])

        if boundary_hikes:
            b_df = pl.DataFrame(boundary_hikes, schema=intra_hikes.schema)
            day_hikes = pl.concat([intra_hikes, b_df])
        else:
            day_hikes = intra_hikes

        if len(day_hikes) == 0:
            continue

        # Extract timing
        day_hikes = day_hikes.with_columns([
            pl.col("local_time").dt.date().alias("date_local"),
            pl.col("local_time").dt.hour().cast(pl.Int32).alias("hour"),
            pl.col("local_time").dt.minute().cast(pl.Int32).alias("minute"),
            (pl.col("local_time").dt.hour().cast(pl.Int32) * 60 + pl.col("local_time").dt.minute().cast(pl.Int32)).alias("min_of_day")
        ])

        # Record distribution
        for r in day_hikes.iter_rows(named=True):
            m = r["min_of_day"]
            if 0 <= m < 1440:
                minute_dist[m] += 1
                hourly_counts[r["hour"]] += 1

        # Classify each hike:
        # 1. On-time Noon: 11:55 <= m <= 12:15 (715 to 735)
        # 2. Queue / Lag Delay: 12:16 <= m <= 12:35 (736 to 755)
        # 3. Late Noon: 12:36 <= m <= 12:59 (756 to 779)
        # 4. Morning Off-Hour: 05:00 <= m <= 11:54 (300 to 714)
        # 5. Afternoon/Evening Off-Hour: 13:00 <= m <= 21:59 (780 to 1319)
        # 6. Night Off-Hour: m < 300 or m >= 1320
        day_hikes = day_hikes.with_columns(
            pl.when((pl.col("min_of_day") >= 715) & (pl.col("min_of_day") <= 735))
            .then(pl.lit("on_time_noon"))
            .when((pl.col("min_of_day") >= 736) & (pl.col("min_of_day") <= 755))
            .then(pl.lit("queue_lag"))
            .when((pl.col("min_of_day") >= 756) & (pl.col("min_of_day") < 780))
            .then(pl.lit("late_noon"))
            .when((pl.col("min_of_day") >= 300) & (pl.col("min_of_day") < 715))
            .then(pl.lit("morning_offhour"))
            .when((pl.col("min_of_day") >= 780) & (pl.col("min_of_day") < 1320))
            .then(pl.lit("afternoon_offhour"))
            .otherwise(pl.lit("night_offhour"))
            .alias("category")
        )

        # Aggregate per station for the day
        st_agg = day_hikes.group_by(["station_uuid", "date_local"]).agg([
            pl.len().alias("total_hikes"),
            (pl.col("category") == "on_time_noon").sum().alias("on_time_noon_hikes"),
            (pl.col("category") == "queue_lag").sum().alias("queue_lag_hikes"),
            (pl.col("category") == "late_noon").sum().alias("late_noon_hikes"),
            (pl.col("category") == "morning_offhour").sum().alias("morning_offhour_hikes"),
            (pl.col("category") == "afternoon_offhour").sum().alias("afternoon_offhour_hikes"),
            (pl.col("category") == "night_offhour").sum().alias("night_offhour_hikes"),
            (pl.col("category").is_in(["morning_offhour", "afternoon_offhour", "night_offhour"])).sum().alias("blatant_offhour_hikes"),
            pl.max_horizontal(["diesel_diff", "e5_diff", "e10_diff"]).max().alias("max_hike_eur")
        ])
        all_station_day_records.append(st_agg)

    print("Aggregating results across all 171 days...")
    full_st_days = pl.concat(all_station_day_records)
    print(f"Total station-day records with at least one hike: {len(full_st_days)}")

    # Overall hike categories
    tot_on_time = full_st_days["on_time_noon_hikes"].sum()
    tot_queue_lag = full_st_days["queue_lag_hikes"].sum()
    tot_late_noon = full_st_days["late_noon_hikes"].sum()
    tot_morning = full_st_days["morning_offhour_hikes"].sum()
    tot_afternoon = full_st_days["afternoon_offhour_hikes"].sum()
    tot_night = full_st_days["night_offhour_hikes"].sum()
    tot_blatant = full_st_days["blatant_offhour_hikes"].sum()
    grand_total_hikes = full_st_days["total_hikes"].sum()

    print("\n" + "="*70)
    print("1. GRAND TOTAL PRICE HIKES BREAKDOWN (2026-04-01 to 2026-09-18)")
    print("="*70)
    print(f"Total Price Hikes Observed: {grand_total_hikes:,}")
    print(f"  - On-Time Noon (11:55 - 12:15):       {tot_on_time:8,d} ({tot_on_time/grand_total_hikes*100:5.2f}%)")
    print(f"  - Technical Lag/Queue (12:16 - 12:35):{tot_queue_lag:8,d} ({tot_queue_lag/grand_total_hikes*100:5.2f}%)")
    print(f"  - Late Noon (12:36 - 12:59):          {tot_late_noon:8,d} ({tot_late_noon/grand_total_hikes*100:5.2f}%)")
    print(f"  - Morning Off-Hour (05:00 - 11:54):   {tot_morning:8,d} ({tot_morning/grand_total_hikes*100:5.2f}%)")
    print(f"  - Afternoon Off-Hour (13:00 - 21:59): {tot_afternoon:8,d} ({tot_afternoon/grand_total_hikes*100:5.2f}%)")
    print(f"  - Night Off-Hour (22:00 - 04:59):     {tot_night:8,d} ({tot_night/grand_total_hikes*100:5.2f}%)")
    print(f"  --> TOTAL BLATANT OFF-HOUR HIKES:     {tot_blatant:8,d} ({tot_blatant/grand_total_hikes*100:5.2f}%)")

    # Are blatant hikes deliberate (multiple hikes in a day)?
    multi_hike_days = full_st_days.filter(pl.col("total_hikes") > 1)
    blatant_with_noon = full_st_days.filter((pl.col("on_time_noon_hikes") > 0) & (pl.col("blatant_offhour_hikes") > 0))
    blatant_without_noon = full_st_days.filter((pl.col("on_time_noon_hikes") == 0) & (pl.col("blatant_offhour_hikes") > 0))

    print("\n" + "="*70)
    print("2. ANSWERING THE QUESTION: REPORTING LAG VS DELIBERATE VIOLATION")
    print("="*70)
    print(f"Station-days with multiple hikes (>1 hike in a single day): {len(multi_hike_days):,}")
    print(f"Station-days hiking BOTH at Noon AND Off-Hours (e.g. hiked at 12:00 AND hiked again at 16:00): {len(blatant_with_noon):,}")
    print(f"Station-days hiking ONLY off-hours (e.g. hiked at 07:00 or 15:00, skipped 12:00): {len(blatant_without_noon):,}")

    # Top minutes of the day around noon
    print("\nMinute distribution from 11:50 to 12:40:")
    for m in range(710, 761, 5):
        h = m // 60
        mn = m % 60
        count_5m = sum(minute_dist[m:m+5])
        print(f"  {h:02d}:{mn:02d} - {h:02d}:{mn+4:02d}: {count_5m:7,d} hikes")

    # Hourly distribution
    print("\nFull 24-Hour Distribution of Price Hikes:")
    for h in range(24):
        pct = hourly_counts[h] / grand_total_hikes * 100
        bar = "#" * int(pct * 2)
        print(f"  Hour {h:02d}:00: {hourly_counts[h]:8,d} ({pct:5.2f}%)  {bar}")

    # Station Aggregations for Name & Shame
    st_summary = full_st_days.group_by("station_uuid").agg([
        pl.len().alias("active_days_with_hikes"),
        pl.col("total_hikes").sum().alias("total_hikes_count"),
        pl.col("blatant_offhour_hikes").sum().alias("blatant_violations_count"),
        (pl.col("blatant_offhour_hikes") > 0).sum().alias("days_with_blatant_violation"),
        (pl.col("total_hikes") > 1).sum().alias("days_with_multiple_hikes"),
        pl.col("queue_lag_hikes").sum().alias("queue_lag_events"),
        pl.col("morning_offhour_hikes").sum().alias("morning_violations"),
        pl.col("afternoon_offhour_hikes").sum().alias("afternoon_violations"),
        pl.col("night_offhour_hikes").sum().alias("night_violations"),
        pl.col("max_hike_eur").max().alias("max_hike_eur")
    ]).join(stations, left_on="station_uuid", right_on="uuid", how="inner")

    # Filter stations that actually had blatant violations
    offenders = st_summary.filter(pl.col("blatant_violations_count") > 0)
    print(f"\nTotal Stations with at least 1 blatant off-hour violation: {len(offenders):,} / {len(stations):,} ({len(offenders)/len(stations)*100:.1f}%)")

    # Top 20 Repeat Offenders
    top20_stations = offenders.sort("blatant_violations_count", descending=True).head(20)
    print("\n" + "="*70)
    print("3. TOP 20 OFFENDING STATIONS (NAME & SHAME)")
    print("="*70)
    for idx, s in enumerate(top20_stations.iter_rows(named=True), 1):
        print(f"{idx:2d}. {s['name']} | Brand: {s['brand']} ({s['corporate_group']})")
        print(f"    Location: {s['street']}, {s['post_code']} {s['city']} ({s['region']})")
        print(f"    Violations: {s['blatant_violations_count']} off-hour hikes across {s['days_with_blatant_violation']} days | Multi-hike days: {s['days_with_multiple_hikes']} | Max hike: +{s['max_hike_eur']:.3f} €/L")
        print(f"    Breakdown: Morning: {s['morning_violations']} | Afternoon: {s['afternoon_violations']} | Night: {s['night_violations']}")

    # Top 15 Offending PLZ 5-digit
    print("\n" + "="*70)
    print("4. TOP 15 OFFENDING POSTAL CODES (5-Digit PLZ)")
    print("="*70)
    top_plz5 = offenders.group_by("post_code").agg([
        pl.len().alias("offending_stations"),
        pl.col("blatant_violations_count").sum().alias("total_violations"),
        pl.col("days_with_multiple_hikes").sum().alias("multi_hike_days"),
        pl.col("city").first().alias("city"),
        pl.col("region").first().alias("region")
    ]).sort("total_violations", descending=True).head(15)
    for idx, p in enumerate(top_plz5.iter_rows(named=True), 1):
        print(f"{idx:2d}. PLZ {p['post_code']} ({p['city']}, {p['region']}): {p['total_violations']} violations across {p['offending_stations']} station(s) | {p['multi_hike_days']} multi-hike days")

    # Top 10 Offending 2-Digit PLZ Zones
    offenders = offenders.with_columns(pl.col("post_code").str.slice(0, 2).alias("plz_2"))
    print("\n" + "="*70)
    print("5. TOP 10 OFFENDING 2-DIGIT POSTAL REGIONS (LEITBEREICHE)")
    print("="*70)
    top_plz2 = offenders.group_by("plz_2").agg([
        pl.len().alias("offending_stations"),
        pl.col("blatant_violations_count").sum().alias("total_violations"),
        pl.col("days_with_multiple_hikes").sum().alias("multi_hike_days")
    ]).sort("total_violations", descending=True).head(10)
    for idx, p in enumerate(top_plz2.iter_rows(named=True), 1):
        print(f"{idx:2d}. PLZ {p['plz_2']}xxx: {p['total_violations']:,} violations across {p['offending_stations']} station(s) | {p['multi_hike_days']} multi-hike days")

    # Offending Regions
    print("\n" + "="*70)
    print("6. REGIONAL BREAKDOWN (FEDERAL REGIONS)")
    print("="*70)
    # Total stations per region
    reg_totals = stations.group_by("region").agg(pl.len().alias("total_network_stations"))
    reg_agg = offenders.group_by("region").agg([
        pl.len().alias("offending_stations"),
        pl.col("blatant_violations_count").sum().alias("total_violations"),
        pl.col("days_with_multiple_hikes").sum().alias("multi_hike_days")
    ]).join(reg_totals, on="region", how="left").with_columns(
        (pl.col("offending_stations") / pl.col("total_network_stations") * 100).round(1).alias("offender_pct")
    ).sort("total_violations", descending=True)
    for idx, r in enumerate(reg_agg.iter_rows(named=True), 1):
        print(f"{idx:2d}. {r['region']}: {r['total_violations']:,} violations | {r['offending_stations']}/{r['total_network_stations']} stations ({r['offender_pct']}%) | {r['multi_hike_days']} multi-hike days")

    # Offending Corporate Groups
    print("\n" + "="*70)
    print("7. CORPORATE GROUP / BRAND BREAKDOWN")
    print("="*70)
    group_totals = stations.group_by("corporate_group").agg(pl.len().alias("total_network_stations"))
    group_agg = offenders.group_by("corporate_group").agg([
        pl.len().alias("offending_stations"),
        pl.col("blatant_violations_count").sum().alias("total_violations"),
        pl.col("days_with_multiple_hikes").sum().alias("multi_hike_days")
    ]).join(group_totals, on="corporate_group", how="left").with_columns(
        (pl.col("offending_stations") / pl.col("total_network_stations") * 100).round(1).alias("offender_pct")
    ).sort("total_violations", descending=True)
    for idx, g in enumerate(group_agg.iter_rows(named=True), 1):
        print(f"{idx:2d}. {g['corporate_group']}: {g['total_violations']:,} violations | {g['offending_stations']}/{g['total_network_stations']} stations ({g['offender_pct']}%)")

    # Save summary parquet files for dashboard integration
    os.makedirs("data/dashboard", exist_ok=True)
    st_summary.write_parquet("data/dashboard/station_compliance_summary.parquet")
    print("\nSaved station compliance summary to data/dashboard/station_compliance_summary.parquet")

if __name__ == "__main__":
    analyze_compliance()
