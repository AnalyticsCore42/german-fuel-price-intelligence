"""
Quick empirical test of alternative national-average weighting schemes.

Compares the current dashboard national average (unweighted mean of
station-hour observations) against:
  1. Station-count-weighted: weight each region by its number of stations.
  2. Population-weighted: weight each region by an approximate population
     derived from the German states listed in the region label.

Input files:
  - data/processed_daily_margins.parquet
  - data/processed_regional_daily_margins.parquet

Output:
  - Prints summary statistics for E5, E10 and diesel.
  - Saves scripts/exploratory/weighting_comparison_{fuel}.csv
  - Saves scripts/exploratory/weighting_comparison_{fuel}.html (Plotly chart)

Caveat: The project regions overlap in state coverage (e.g. Baden-Württemberg
appears in three regions), so the population weights are approximate. They are
still useful for a directional check of whether population weighting materially
changes the national picture.
"""
from __future__ import annotations

from collections import Counter
from datetime import date
from pathlib import Path

import polars as pl
import plotly.graph_objects as go

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
OUT_DIR = PROJECT_ROOT / "scripts" / "exploratory"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Approximate 2023 German state populations (millions).
STATE_POPULATION = {
    "Baden-Württemberg": 11.1,
    "Bayern": 13.1,
    "Berlin": 3.7,
    "Brandenburg": 2.5,
    "Bremen": 0.68,
    "Hamburg": 1.85,
    "Hessen": 6.3,
    "Mecklenburg-Vorpommern": 1.6,
    "Niedersachsen": 8.0,
    "Nordrhein-Westfalen": 17.9,
    "Rheinland-Pfalz": 4.1,
    "Saarland": 1.0,
    "Sachsen": 4.0,
    "Sachsen-Anhalt": 2.2,
    "Schleswig-Holstein": 2.9,
    "Thüringen": 2.1,
}

# Mapping from the project's region labels to the states they cover.
# These regions are not a strict partition, so population weights are
# approximate (state population is divided by the number of regions that
# mention it).
REGION_STATES: dict[str, list[str]] = {
    "North (Hamburg/Schleswig-Holstein/Bremen/N.Lower Saxony)": [
        "Hamburg", "Schleswig-Holstein", "Bremen", "Niedersachsen"
    ],
    "Northeast (Berlin/Brandenburg/Mecklenburg)": [
        "Berlin", "Brandenburg", "Mecklenburg-Vorpommern"
    ],
    "West (W.Westphalia/W.Lower Saxony)": [
        "Nordrhein-Westfalen", "Niedersachsen"
    ],
    "West-Central (S.Westphalia/Rhineland-Palatinate/Saarland)": [
        "Nordrhein-Westfalen", "Rheinland-Pfalz", "Saarland"
    ],
    "Central (Hesse/C.Lower Saxony/W.Thuringia/E.Westphalia)": [
        "Hessen", "Niedersachsen", "Thüringen", "Nordrhein-Westfalen"
    ],
    "Southwest (S.Hesse/Rhineland-Palatinate/N.Baden-Württemberg)": [
        "Hessen", "Rheinland-Pfalz", "Baden-Württemberg"
    ],
    "Southwest (S.Baden-Württemberg)": ["Baden-Württemberg"],
    "South (S.Bavaria/SE.Baden-Württemberg)": ["Bayern", "Baden-Württemberg"],
    "Southeast (N.Bavaria/S.Thuringia)": ["Bayern", "Thüringen"],
    "East (Saxony/Thuringia/S.Brandenburg)": ["Sachsen", "Thüringen", "Brandenburg"],
}


def _region_population_weights() -> dict[str, float]:
    """Return approximate population weight (millions) for each region."""
    state_region_count: Counter[str] = Counter()
    for states in REGION_STATES.values():
        for state in states:
            state_region_count[state] += 1

    weights: dict[str, float] = {}
    for region, states in REGION_STATES.items():
        weights[region] = sum(
            STATE_POPULATION[state] / state_region_count[state] for state in states
        )
    return weights


def _build_weighted_series(
    regional: pl.DataFrame,
    fuel: str,
    latest_counts: pl.DataFrame,
    region_pop: dict[str, float],
) -> pl.DataFrame:
    """Compute station-count and population weighted national averages."""
    price_col = f"price_{fuel}"
    base = regional.filter(pl.col("region") != "Unknown Region")

    station_weighted = (
        base.join(latest_counts, on="region", how="left")
        .group_by("date")
        .agg(
            (pl.col(price_col) * pl.col("station_count")).sum()
            / pl.col("station_count").sum()
        )
        .rename({price_col: "station_weighted"})
    )

    pop_weighted = (
        base.with_columns(
            pl.col("region").replace(region_pop).cast(pl.Float64).alias("pop_weight")
        )
        .group_by("date")
        .agg(
            (pl.col(price_col) * pl.col("pop_weight")).sum()
            / pl.col("pop_weight").sum()
        )
        .rename({price_col: "pop_weighted"})
    )

    return station_weighted.join(pop_weighted, on="date", how="inner")


def _make_chart(df: pl.DataFrame, fuel: str) -> None:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["date"].to_list(),
            y=df["diff_stat_ct"].to_list(),
            mode="lines",
            name="Station-count weighted",
            line={"color": "#1f77b4"},
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df["date"].to_list(),
            y=df["diff_pop_ct"].to_list(),
            mode="lines",
            name="Population weighted",
            line={"color": "#ff7f0e"},
        )
    )
    fig.add_hline(y=0, line_dash="dot", line_color="gray")
    fig.update_layout(
        title=f"Weighted national average minus current dashboard average — {fuel.upper()}",
        xaxis_title="Date",
        yaxis_title="Difference (ct/L)",
        hovermode="x unified",
        template="plotly_white",
    )
    fig.write_html(OUT_DIR / f"weighting_comparison_{fuel}.html")


def main() -> None:
    daily = pl.read_parquet(DATA_DIR / "processed_daily_margins.parquet")
    regional = pl.read_parquet(DATA_DIR / "processed_regional_daily_margins.parquet")

    latest_counts = (
        regional.group_by("region")
        .agg(pl.col("station_count").max().alias("station_count"))
    )
    region_pop = _region_population_weights()

    print("Approximate region population weights (millions):")
    for region, weight in sorted(region_pop.items(), key=lambda kv: -kv[1]):
        cnt = latest_counts.filter(pl.col("region") == region)["station_count"][0]
        print(f"  {region[:45]:45s} stations={cnt:4d}  pop={weight:.2f}M")

    for fuel in ("e5", "e10", "diesel"):
        price_col = f"price_{fuel}"
        current = daily.select(["date", price_col]).rename({price_col: "current"})
        weighted = _build_weighted_series(regional, fuel, latest_counts, region_pop)

        comp = current.join(weighted, on="date", how="inner").with_columns(
            [
                ((pl.col("station_weighted") - pl.col("current")) * 100).alias(
                    "diff_stat_ct"
                ),
                ((pl.col("pop_weighted") - pl.col("current")) * 100).alias(
                    "diff_pop_ct"
                ),
            ]
        )

        comp.write_csv(OUT_DIR / f"weighting_comparison_{fuel}.csv")
        _make_chart(comp, fuel)

        pre_2024 = comp.filter(pl.col("date") < date(2024, 1, 1))
        post_2024 = comp.filter(pl.col("date") >= date(2024, 1, 1))

        print(f"\n=== {fuel.upper()} ===")
        print(f"  Full period mean abs diff:")
        print(f"    Station-count weighted: {comp['diff_stat_ct'].abs().mean():.3f} ct/L")
        print(f"    Population weighted:    {comp['diff_pop_ct'].abs().mean():.3f} ct/L")
        print(f"  Max signed diff:")
        print(f"    Station-count weighted: {comp['diff_stat_ct'].max():.3f} ct/L")
        print(f"    Population weighted:    {comp['diff_pop_ct'].max():.3f} ct/L")
        print(f"  Days with pop-weighted diff > 2 ct/L: {(comp['diff_pop_ct'].abs() > 2.0).sum()}")
        print(f"  Pre-2024 mean abs diff: station={pre_2024['diff_stat_ct'].abs().mean():.3f}, pop={pre_2024['diff_pop_ct'].abs().mean():.3f} ct/L")
        print(f"  2024+ mean abs diff:    station={post_2024['diff_stat_ct'].abs().mean():.3f}, pop={post_2024['diff_pop_ct'].abs().mean():.3f} ct/L")

    print(f"\nOutputs saved to {OUT_DIR}/weighting_comparison_*.csv and .html")


if __name__ == "__main__":
    main()
