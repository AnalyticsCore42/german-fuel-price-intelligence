"""
Comprehensive Forensic Pattern Analysis of Price Hikes across all ESSO (EG Group) Stations.
Audits the period April 1 to September 18, 2026 under the Kraftstoffpreisanpassungsgesetz (§ 3 KPAnG).

Checks:
1. Are afternoon price hikes randomly distributed (human error / random glitched drops)?
2. Or do they follow rigid algorithmic structures (fixed minute schedules, synchronized batches, automated rebounds)?
3. What is the distribution of time deltas between a drop and subsequent hike (flash rebounds)?
4. Comparison with ARAL and SHELL.
"""

import glob
from pathlib import Path
import polars as pl

DATA_DIR = Path("data")

def main():
    print("==========================================")
    print("1. LOADING STATIONS & INITIALIZING SCAN")
    print("==========================================")
    stations = pl.read_parquet(DATA_DIR / "tankerkoenig" / "stations" / "cleaned-stations.parquet")
    esso_stations = stations.filter(pl.col("brand") == "ESSO")
    aral_stations = stations.filter(pl.col("brand") == "ARAL")
    shell_stations = stations.filter(pl.col("brand") == "SHELL")

    esso_uuids = set(esso_stations["uuid"].to_list())
    aral_uuids = set(aral_stations["uuid"].to_list())
    shell_uuids = set(shell_stations["uuid"].to_list())

    print(f"ESSO stations:  {len(esso_uuids):,}")
    print(f"ARAL stations:  {len(aral_uuids):,}")
    print(f"SHELL stations: {len(shell_uuids):,}")

    price_files = sorted(glob.glob(str(DATA_DIR / "tankerkoenig" / "prices" / "2026" / "2026-0[4-9]-*.parquet")))
    print(f"Scanning {len(price_files)} daily price files (Apr–Sep 2026)...")

    # ==========================================
    # 2. EXTRACTING ESSO PRICE TRANSITIONS
    # ==========================================
    # We collect price transitions for ESSO
    q_esso = (
        pl.scan_parquet(price_files)
        .filter(pl.col("station_uuid").is_in(esso_uuids))
        .select(["date", "station_uuid", "e5"])
        .filter(pl.col("e5") > 0)
    )
    df_esso = q_esso.collect()
    print(f"Total ESSO raw price rows: {df_esso.height:,}")

    # Convert to Berlin time and sort
    df_esso = (
        df_esso.sort(["station_uuid", "date"])
        .with_columns([
            pl.col("date").dt.convert_time_zone("Europe/Berlin").alias("local_time"),
            pl.col("e5").alias("price"),
            pl.col("e5").shift(1).over("station_uuid").alias("prev_price"),
            pl.col("date").dt.convert_time_zone("Europe/Berlin").shift(1).over("station_uuid").alias("prev_time"),
        ])
        .filter(
            (pl.col("prev_price").is_not_null()) &
            (pl.col("prev_price") > 0) &
            ((pl.col("price") - pl.col("prev_price")).abs() > 0.001)
        )
        .with_columns([
            (pl.col("price") - pl.col("prev_price")).alias("diff"),
            ((pl.col("price") - pl.col("prev_price")) * 100).round(1).alias("diff_ct"),
            ((pl.col("local_time") - pl.col("prev_time")).dt.total_seconds()).alias("sec_since_prev"),
            pl.col("local_time").dt.hour().alias("hour"),
            pl.col("local_time").dt.minute().alias("minute"),
            pl.col("local_time").dt.time().alias("time_of_day"),
            pl.col("local_time").dt.date().alias("local_date"),
        ])
    )
    print(f"Total ESSO non-zero price transitions: {df_esso.height:,}")

    # ==========================================
    # 3. AFTERNOON HIKES ANALYSIS (AFTER 13:00)
    # ==========================================
    afternoon_hikes = df_esso.filter(
        (pl.col("hour") >= 13) &
        (pl.col("diff") > 0.001)
    )
    print(f"\n==========================================")
    print(f"TOTAL AFTERNOON HIKES ACROSS ALL ESSO STATIONS (AFTER 13:00): {afternoon_hikes.height:,}")
    print(f"==========================================")

    # A. Minute of the hour distribution
    print("\n--- Top 10 Minutes of the Hour for Afternoon Hikes ---")
    min_dist = afternoon_hikes.group_by("minute").len().sort("len", descending=True).head(10)
    for row in min_dist.iter_rows(named=True):
        pct = (row['len'] / afternoon_hikes.height) * 100
        print(f"Minute :{row['minute']:02d} -> {row['len']:,} hikes ({pct:.1f}%)")

    # B. Exact Time of Day clusters (Synchronized batch execution)
    print("\n--- Top 15 Exact Timestamps with Largest Batch Pushes ---")
    batch_dist = afternoon_hikes.group_by("local_time").agg([
        pl.len().alias("station_count"),
        pl.col("diff_ct").mean().alias("avg_diff_ct"),
        pl.col("station_uuid").n_unique().alias("unique_stations"),
    ]).sort("station_count", descending=True).head(15)
    for row in batch_dist.iter_rows(named=True):
        print(f"{row['local_time'].strftime('%Y-%m-%d %H:%M:%S')} -> {row['station_count']} stations hiked simultaneously (Avg hike: +{row['avg_diff_ct']:.1f} ct)")

    # C. Hourly distribution of afternoon hikes
    print("\n--- Hourly Distribution of Afternoon Hikes ---")
    hour_dist = afternoon_hikes.group_by("hour").len().sort("hour")
    for row in hour_dist.iter_rows(named=True):
        pct = (row['len'] / afternoon_hikes.height) * 100
        print(f"{row['hour']:02d}:00 Uhr -> {row['len']:,} hikes ({pct:.1f}%)")

    # D. "Flash Rebounds" (Drop followed by Hike within < 15 min)
    # Let's inspect sec_since_prev for afternoon hikes
    print("\n--- Time Elapsed Since Previous Price Change (Seconds / Minutes) ---")
    under_2min = afternoon_hikes.filter(pl.col("sec_since_prev") <= 120).height
    under_5min = afternoon_hikes.filter(pl.col("sec_since_prev") <= 300).height
    under_15min = afternoon_hikes.filter(pl.col("sec_since_prev") <= 900).height
    under_30min = afternoon_hikes.filter(pl.col("sec_since_prev") <= 1800).height
    over_30min = afternoon_hikes.filter(pl.col("sec_since_prev") > 1800).height

    print(f"Hike within <= 2 minutes of prior change:  {under_2min:,} ({under_2min/afternoon_hikes.height*100:.1f}%)")
    print(f"Hike within <= 5 minutes of prior change:  {under_5min:,} ({under_5min/afternoon_hikes.height*100:.1f}%)")
    print(f"Hike within <= 15 minutes of prior change: {under_15min:,} ({under_15min/afternoon_hikes.height*100:.1f}%)")
    print(f"Hike within <= 30 minutes of prior change: {under_30min:,} ({under_30min/afternoon_hikes.height*100:.1f}%)")
    print(f"Hike after > 30 minutes of prior change:   {over_30min:,} ({over_30min/afternoon_hikes.height*100:.1f}%)")

    # E. Typical Price Hike magnitudes (diff_ct)
    print("\n--- Most Common Hike Amounts (Cent/Liter) ---")
    amount_dist = afternoon_hikes.group_by("diff_ct").len().sort("len", descending=True).head(10)
    for row in amount_dist.iter_rows(named=True):
        pct = (row['len'] / afternoon_hikes.height) * 100
        print(f"+{row['diff_ct']:4.1f} ct -> {row['len']:,} occurrences ({pct:.1f}%)")

    # ==========================================
    # 4. BENCHMARK COMPARISON: ARAL & SHELL
    # ==========================================
    print("\n==========================================")
    print("4. BENCHMARK COMPARISON: ARAL & SHELL AFTERNOON HIKES")
    print("==========================================")
    
    q_bench = (
        pl.scan_parquet(price_files)
        .filter(pl.col("station_uuid").is_in(aral_uuids.union(shell_uuids)))
        .select(["date", "station_uuid", "e5"])
        .filter(pl.col("e5") > 0)
    )
    df_bench = q_bench.collect()
    df_bench = (
        df_bench.sort(["station_uuid", "date"])
        .with_columns([
            pl.col("date").dt.convert_time_zone("Europe/Berlin").alias("local_time"),
            pl.col("e5").alias("price"),
            pl.col("e5").shift(1).over("station_uuid").alias("prev_price"),
        ])
        .filter(
            (pl.col("prev_price").is_not_null()) &
            (pl.col("prev_price") > 0) &
            ((pl.col("price") - pl.col("prev_price")).abs() > 0.001)
        )
        .with_columns([
            (pl.col("price") - pl.col("prev_price")).alias("diff"),
            pl.col("local_time").dt.hour().alias("hour"),
            pl.when(pl.col("station_uuid").is_in(aral_uuids)).then(pl.lit("ARAL")).otherwise(pl.lit("SHELL")).alias("brand")
        ])
    )
    bench_afternoon = df_bench.filter(
        (pl.col("hour") >= 13) &
        (pl.col("diff") > 0.001)
    )
    print(f"ARAL afternoon hikes (total across {len(aral_uuids)} stations):  {bench_afternoon.filter(pl.col('brand')=='ARAL').height:,}")
    print(f"SHELL afternoon hikes (total across {len(shell_uuids)} stations): {bench_afternoon.filter(pl.col('brand')=='SHELL').height:,}")
    print(f"ESSO afternoon hikes (total across {len(esso_uuids)} stations):  {afternoon_hikes.height:,}")

if __name__ == "__main__":
    main()
