"""
Tests for the RBOB summer/winter grade re-timing in src/gasprice/fetch_refined_product_baseline.py.

Why these tests matter:
The RB=F front month changes gasoline grade at the March and September contract rolls, one to two
months before German stations do. Without re-timing, every September the wholesale proxy drops by
several ct/L while German costs have not changed yet, which inflates the retail spread and distorts
pass-through estimates around the autumn Tankrabatt.
"""
from __future__ import annotations

from datetime import date, timedelta

import polars as pl
import pytest

from gasprice.build_dashboard_dataset import DERIVED_COLUMNS
from gasprice.fetch_refined_product_baseline import (
    AUTUMN_JUMP_SHARE,
    SPRING_JUMP_SHARE,
    align_gasoline_grade_to_germany,
)


def _synthetic_year(spring_jump: float, autumn_jump: float) -> pl.DataFrame:
    """Flat Brent and RBOB, with the grade jumps on the first weekday of March and September."""
    rows = []
    rbob = 2.0
    d = date(2025, 1, 1)
    while d <= date(2025, 12, 31):
        if d == date(2025, 3, 3):      # first weekday of March 2025
            rbob += spring_jump
        if d == date(2025, 9, 1):      # first weekday of September 2025
            rbob += autumn_jump
        rows.append({"date": d, "rbob_usd_gallon": rbob, "brent_usd_barrel": 70.0, "rb_traded": d.weekday() < 5})
        d += timedelta(days=1)
    return pl.DataFrame(rows)


def _adj(df: pl.DataFrame, day: date) -> float:
    return df.filter(pl.col("date") == day)["gasoline_grade_adj_usd_gallon"].item()


def test_autumn_jump_is_offset_until_german_transition_then_phased_out():
    out = align_gasoline_grade_to_germany(_synthetic_year(spring_jump=0.0, autumn_jump=-0.20))

    assert _adj(out, date(2025, 8, 29)) == 0.0                       # before the roll
    full = 0.20 * AUTUMN_JUMP_SHARE
    assert _adj(out, date(2025, 9, 15)) == pytest.approx(full)       # US winter, Germany still summer
    assert _adj(out, date(2025, 9, 30)) == pytest.approx(full)
    assert 0.0 < _adj(out, date(2025, 10, 23)) < full                # German transition period
    assert _adj(out, date(2025, 11, 15)) == pytest.approx(0.0)
    assert _adj(out, date(2025, 12, 1)) == 0.0
    # Adjusted RBOB keeps the German share of the summer premium through September
    sep = out.filter(pl.col("date") == date(2025, 9, 15))["rbob_usd_gallon"].item()
    assert sep == pytest.approx(2.0 - 0.20 + full)


def test_spring_jump_is_removed_until_german_transition():
    out = align_gasoline_grade_to_germany(_synthetic_year(spring_jump=0.15, autumn_jump=0.0))

    full = 0.15 * SPRING_JUMP_SHARE
    assert _adj(out, date(2025, 3, 10)) == pytest.approx(-full)      # US summer, Germany still winter
    assert -full < _adj(out, date(2025, 4, 10)) < 0.0
    assert _adj(out, date(2025, 5, 1)) == 0.0
    mar = out.filter(pl.col("date") == date(2025, 3, 10))["rbob_usd_gallon"].item()
    assert mar == pytest.approx(2.0 + 0.15 - full)


def test_jumps_in_the_wrong_direction_are_ignored():
    # A crash on the March roll day (e.g. 2020) must not be treated as a grade premium.
    out = align_gasoline_grade_to_germany(_synthetic_year(spring_jump=-0.30, autumn_jump=0.10))
    assert out["gasoline_grade_adj_usd_gallon"].abs().max() == 0.0


def test_derived_column_pattern_keeps_raw_price_columns():
    cols = [
        "date", "price_e5", "price_diesel", "stations_reporting", "station_count", "changes_e5",
        "analysis_level", "comparison_group", "region",
        "Raw_Material_EUR_per_Liter", "brent_eur_liter", "e5_product_eur_liter", "e5_vat", "e5_ebv",
        "e5_co2", "e5_energy", "e5_net_price", "margin_e5", "retail_margin_diesel", "refining_spread_e10",
    ]
    df = pl.DataFrame({c: [] for c in cols})
    kept = df.select(pl.exclude(DERIVED_COLUMNS)).columns
    assert kept == ["date", "price_e5", "price_diesel", "stations_reporting", "station_count",
                    "changes_e5", "analysis_level", "comparison_group", "region"]
