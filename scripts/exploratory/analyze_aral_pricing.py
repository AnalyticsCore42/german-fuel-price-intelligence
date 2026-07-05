"""
Exploratory analysis: ARAL pricing patterns before the KPAnG 12:00-price rule.

Goal: understand when and how ARAL changes prices, and whether there are
systematic patterns that extract more money from customers during high-demand
periods (commute hours, weekends, etc.).

This script is intentionally standalone and exploratory. It writes summary
CSVs and Plotly HTML charts under scripts/exploratory/aral_analysis/.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

import numpy as np
import polars as pl
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
PRICES_DIR = DATA_DIR / "tankerkoenig" / "prices"
STATIONS_FILE = DATA_DIR / "tankerkoenig" / "stations" / "cleaned-stations.parquet"
OUTPUT_DIR = Path(__file__).resolve().parent / "aral_analysis"
OUTPUT_DIR.mkdir(exist_ok=True)

FUELS = ["diesel", "e5", "e10"]


def load_aral_uuids() -> set[str]:
    """Return the set of ARAL station UUIDs."""
    stations = pl.read_parquet(STATIONS_FILE)
    return set(
        stations
        .filter(pl.col("brand").str.to_uppercase() == "ARAL")
        .select(pl.col("uuid").cast(pl.String))
        .to_series()
        .to_list()
    )


def read_aral_file(path: Path, aral_uuids: set[str]) -> pl.DataFrame | None:
    """Read a single daily parquet file and keep only ARAL rows."""
    df = pl.read_parquet(
        path,
        columns=["date", "station_uuid", "diesel", "e5", "e10"],
    )
    df = df.filter(pl.col("station_uuid").is_in(aral_uuids))
    if df.is_empty():
        return None

    return (
        df.with_columns(pl.col("date").dt.convert_time_zone("Europe/Berlin").alias("local_time"))
        .with_columns([
            pl.col("local_time").dt.date().alias("day"),
            pl.col("local_time").dt.hour().cast(pl.Int64).alias("hour"),
            pl.col("local_time").dt.weekday().cast(pl.Int64).alias("weekday"),
        ])
        .sort(["station_uuid", "local_time"])
    )


def detect_changes(df: pl.DataFrame) -> dict[str, pl.DataFrame]:
    """
    For each fuel, detect true price changes per station using vectorised Polars
    operations. Returns one DataFrame per fuel.
    """
    changes: dict[str, pl.DataFrame] = {}

    for fuel in FUELS:
        shifted = (
            df.sort(["station_uuid", "local_time"])
            .with_columns([
                pl.col(fuel).shift(1).over("station_uuid").alias("old_price"),
                pl.col("station_uuid").shift(1).over("station_uuid").alias("prev_station"),
            ])
            .filter(
                (pl.col("station_uuid") == pl.col("prev_station"))
                & pl.col(fuel).is_not_null()
                & pl.col("old_price").is_not_null()
                & (pl.col(fuel) != pl.col("old_price"))
            )
            .with_columns([
                (pl.col(fuel) - pl.col("old_price")).alias("delta"),
                pl.col(fuel).alias("new_price"),
            ])
            .select([
                "station_uuid",
                "local_time",
                "day",
                "weekday",
                "hour",
                "old_price",
                "new_price",
                "delta",
            ])
        )
        changes[fuel] = shifted

    return changes


def aggregate_patterns(all_changes: dict[str, pl.DataFrame]) -> dict[str, dict]:
    """Aggregate change patterns by hour and weekday."""
    result = {}
    for fuel in FUELS:
        df = all_changes[fuel]
        if df.is_empty():
            result[fuel] = {}
            continue

        hourly = (
            df.group_by("hour")
            .agg([
                pl.len().alias("change_count"),
                pl.col("delta").filter(pl.col("delta") > 0).len().alias("up_count"),
                pl.col("delta").filter(pl.col("delta") < 0).len().alias("down_count"),
                pl.col("delta").mean().alias("mean_delta"),
                pl.col("delta").filter(pl.col("delta") > 0).mean().alias("mean_up"),
                pl.col("delta").filter(pl.col("delta") < 0).mean().alias("mean_down"),
            ])
            .sort("hour")
        )

        daily = (
            df.group_by("weekday")
            .agg([
                pl.len().alias("change_count"),
                pl.col("delta").filter(pl.col("delta") > 0).len().alias("up_count"),
                pl.col("delta").mean().alias("mean_delta"),
            ])
            .sort("weekday")
        )

        result[fuel] = {"hourly": hourly, "daily": daily}

    return result


def summarize_jump_sizes(all_changes: dict[str, pl.DataFrame]) -> dict[str, dict]:
    """Compute deciles and extreme jumps per fuel."""
    summary = {}
    for fuel in FUELS:
        df = all_changes[fuel]
        if df.is_empty():
            summary[fuel] = {}
            continue

        deltas = df["delta"].to_numpy()
        up = deltas[deltas > 0]
        down = deltas[deltas < 0]

        summary[fuel] = {
            "total_changes": int(len(deltas)),
            "up_changes": int(len(up)),
            "down_changes": int(len(down)),
            "up_share": float(len(up) / len(deltas)) if len(deltas) else None,
            "mean_delta_eur": float(np.mean(deltas)) if len(deltas) else None,
            "median_delta_eur": float(np.median(deltas)) if len(deltas) else None,
            "p99_up_eur": float(np.percentile(up, 99)) if len(up) else None,
            "p99_down_eur": float(np.percentile(down, 1)) if len(down) else None,
        }
    return summary


def save_csvs(patterns: dict, output_dir: Path) -> None:
    """Write hourly and daily CSVs per fuel."""
    for fuel, agg in patterns.items():
        if not agg:
            continue
        agg["hourly"].write_csv(output_dir / f"aral_{fuel}_hourly.csv")
        agg["daily"].write_csv(output_dir / f"aral_{fuel}_daily.csv")


def write_report(summary: dict, output_dir: Path) -> None:
    """Write a small JSON summary of the main findings."""
    report_path = output_dir / "aral_summary.json"
    report_path.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSummary written to: {report_path}")


def create_visualizations(patterns: dict, output_dir: Path) -> None:
    """Create and save Plotly charts for ARAL pricing patterns."""
    for fuel in FUELS:
        agg = patterns.get(fuel, {})
        if not agg:
            continue

        hourly = agg["hourly"]
        daily = agg["daily"]

        fig_hourly = make_subplots(
            rows=2, cols=1,
            subplot_titles=(
                f"ARAL {fuel.upper()}: number of price changes by hour",
                f"ARAL {fuel.upper()}: average price delta by hour",
            ),
            vertical_spacing=0.12,
        )
        fig_hourly.add_trace(
            go.Bar(x=hourly["hour"].to_list(), y=hourly["up_count"].to_list(), name="Up", marker_color="#EF4444"),
            row=1, col=1,
        )
        fig_hourly.add_trace(
            go.Bar(x=hourly["hour"].to_list(), y=hourly["down_count"].to_list(), name="Down", marker_color="#22C55E"),
            row=1, col=1,
        )
        fig_hourly.add_trace(
            go.Bar(x=hourly["hour"].to_list(), y=hourly["mean_delta"].to_list(), name="Mean delta", marker_color="#F5A623"),
            row=2, col=1,
        )
        fig_hourly.update_layout(
            template="plotly_white",
            height=700,
            barmode="group",
            title_text=f"ARAL {fuel.upper()} Intraday Pricing Patterns",
            showlegend=False,
        )
        fig_hourly.write_html(output_dir / f"aral_{fuel}_hourly.html")

        weekday_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        fig_daily = go.Figure()
        fig_daily.add_trace(go.Bar(
            x=weekday_names,
            y=daily["up_count"].to_list(),
            name="Up",
            marker_color="#EF4444",
        ))
        fig_daily.add_trace(go.Bar(
            x=weekday_names,
            y=(daily["change_count"] - daily["up_count"]).to_list(),
            name="Down",
            marker_color="#22C55E",
        ))
        fig_daily.update_layout(
            template="plotly_white",
            barmode="group",
            title=f"ARAL {fuel.upper()}: price changes by weekday",
            xaxis_title="Weekday",
            yaxis_title="Number of changes",
            height=450,
        )
        fig_daily.write_html(output_dir / f"aral_{fuel}_daily.html")

    print(f"Charts written to: {output_dir}")


def main() -> None:
    print("Loading ARAL station UUIDs...")
    aral_uuids = load_aral_uuids()
    print(f"Found {len(aral_uuids):,} ARAL stations")

    price_files = sorted(PRICES_DIR.glob("*/*.parquet"))
    print(f"Processing {len(price_files):,} daily price files...")

    change_parts: dict[str, list[pl.DataFrame]] = {fuel: [] for fuel in FUELS}

    for idx, path in enumerate(price_files, 1):
        df = read_aral_file(path, aral_uuids)
        if df is None:
            continue

        changes = detect_changes(df)
        for fuel in FUELS:
            if not changes[fuel].is_empty():
                change_parts[fuel].append(changes[fuel])

        if idx % 100 == 0 or idx == len(price_files):
            print(f"  processed {idx:,}/{len(price_files):,} files")

    print("\nConcatenating results...")
    all_changes: dict[str, pl.DataFrame] = {
        fuel: pl.concat(parts, how="vertical") if parts else pl.DataFrame(schema={
            "station_uuid": pl.String,
            "local_time": pl.Datetime("us", "Europe/Berlin"),
            "day": pl.Date,
            "weekday": pl.Int64,
            "hour": pl.Int64,
            "old_price": pl.Float64,
            "new_price": pl.Float64,
            "delta": pl.Float64,
        })
        for fuel, parts in change_parts.items()
    }

    print("Aggregating patterns...")
    patterns = aggregate_patterns(all_changes)
    summary = summarize_jump_sizes(all_changes)

    save_csvs(patterns, OUTPUT_DIR)
    write_report(summary, OUTPUT_DIR)
    create_visualizations(patterns, OUTPUT_DIR)

    print("\n=== ARAL Price Change Summary ===")
    for fuel in FUELS:
        s = summary.get(fuel, {})
        if not s:
            continue
        print(f"\n{fuel.upper()}:")
        print(f"  Total changes:       {s['total_changes']:,}")
        print(f"  Upward changes:      {s['up_changes']:,} ({s['up_share']:.1%})")
        print(f"  Mean delta:          {s['mean_delta_eur']:+.4f} €/L")
        print(f"  Median delta:        {s['median_delta_eur']:+.4f} €/L")
        print(f"  99th percentile up:  +{s['p99_up_eur']:.4f} €/L")
        print(f"  99th percentile down:{s['p99_down_eur']:.4f} €/L")

    print(f"\nOutputs in: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
