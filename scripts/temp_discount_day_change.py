"""
Temp script: compute per-station and national-average fuel-price changes
on the day before vs. the day of / day after each German fuel-tax discount.
"""
from __future__ import annotations

import polars as pl
from pathlib import Path
from datetime import date, timedelta

ROOT = Path(__file__).resolve().parents[1]
PRICES_DIR = ROOT / "data" / "tankerkoenig" / "prices"

FUELS = {"e5": "Super E5", "e10": "Super E10", "diesel": "Diesel"}

EVENTS = {
    "1st Tax Break (2022)": date(2022, 6, 1),
    "2nd Tax Break (2026)": date(2026, 5, 1),
}


def load_day(d: date) -> pl.DataFrame | None:
    path = PRICES_DIR / str(d.year) / f"{d}.parquet"
    if not path.exists():
        print(f"  [!] missing file: {path}")
        return None
    return pl.read_parquet(path)


def latest_price_per_station(df: pl.DataFrame, fuel: str) -> pl.DataFrame:
    """Keep the latest observation per station for the requested fuel."""
    col = fuel
    return (
        df.filter(pl.col(col) > 0)
        .sort("date")
        .group_by("station_uuid")
        .agg(pl.col(col).last().alias("price"))
    )


def compute_event(start: date, event_name: str) -> None:
    print(f"\n{'='*60}")
    print(f"Event: {event_name} — starts {start}")
    print(f"{'='*60}")

    pre_day = start - timedelta(days=1)
    post_day = start + timedelta(days=1)

    df_pre = load_day(pre_day)
    df_start = load_day(start)
    df_post = load_day(post_day)

    if df_pre is None or df_start is None or df_post is None:
        print("  Skipping: one or more daily files missing.")
        return

    for fuel, label in FUELS.items():
        pre = latest_price_per_station(df_pre, fuel)
        start_day = latest_price_per_station(df_start, fuel)
        post = latest_price_per_station(df_post, fuel)

        # join pre -> start and pre -> post
        chg_start = pre.join(start_day, on="station_uuid", suffix="_start")
        chg_post = pre.join(post, on="station_uuid", suffix="_post")

        chg_start = chg_start.with_columns(
            (pl.col("price_start") - pl.col("price")).alias("delta")
        )
        chg_post = chg_post.with_columns(
            (pl.col("price_post") - pl.col("price")).alias("delta")
        )

        print(f"\n  {label} ({fuel})")
        print(f"    Matched stations: pre→start {chg_start.height:,}, pre→post {chg_post.height:,}")

        for desc, df_chg in [("pre day → start day", chg_start), ("pre day → day after", chg_post)]:
            if df_chg.is_empty():
                continue
            stats = df_chg.select(
                pl.col("delta").mean().alias("mean_delta"),
                pl.col("delta").median().alias("median_delta"),
                pl.col("delta").min().alias("min_delta"),
                pl.col("delta").max().alias("max_delta"),
                pl.col("delta").std().alias("std_delta"),
            ).to_dicts()[0]

            nat_pre = df_chg["price"].mean()
            nat_post_col = "price_start" if "start" in desc else "price_post"
            nat_post = df_chg[nat_post_col].mean()
            nat_delta = nat_post - nat_pre

            print(f"      {desc}:")
            print(f"        national avg price: €{nat_pre:.3f} → €{nat_post:.3f} (Δ €{nat_delta:+.3f}/L)")
            print(f"        per-station Δ: mean={stats['mean_delta']:+.3f}, median={stats['median_delta']:+.3f}")
            print(f"        per-station range: min={stats['min_delta']:+.3f}, max={stats['max_delta']:+.3f}")


if __name__ == "__main__":
    for name, start in EVENTS.items():
        compute_event(start, name)
