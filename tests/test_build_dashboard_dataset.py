"""
Tests for src/gasprice/build_dashboard_dataset.py.

Why these tests matter:
This module is the heart of the ETL pipeline. It turns raw Tankerkönig
station-hour observations into the daily/hourly/brand/regional datasets that
the dashboard consumes. The tests below focus on the small, pure functions that
are easy to verify with synthetic data but whose correctness has outsized impact
on every chart and KPI.

We do NOT test the full build_dashboard_datasets() orchestrator here because it
reads 5 GB of raw parquet files and is inherently an integration test. Those
large functions are exercised by running scripts/run_pipeline.py manually.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import polars as pl
import pytest

from gasprice.build_dashboard_dataset import (
    MIN_BRAND_STATIONS,
    OTHER_BRAND_BUCKET,
    _run_quality_checks,
    _validate_incremental_inputs,
    build_hourly_snapshot,
    compute_daily_price_changes,
    summarize_brand_daily,
    summarize_daily,
    summarize_hourly,
    summarize_regional_daily,
    valid_price,
)


# ---------------------------------------------------------------------------
# 1. Price validation
# ---------------------------------------------------------------------------
def test_valid_price_filters_out_invalid_values():
    """
    valid_price() is the first data-quality gate. If it starts accepting
    negative prices or impossible values > 3 EUR/L, every downstream average,
    margin, and KPI will be corrupted.
    """
    df = pl.DataFrame(
        {
            "diesel": [0.5, 1.2, 2.0, 3.5, -0.1, None],
        }
    )
    result = df.with_columns(valid_price("diesel").alias("valid"))
    assert result["valid"].to_list() == [None, 1.2, 2.0, None, None, None]


# ---------------------------------------------------------------------------
# 2. Hourly snapshot reconstruction
# ---------------------------------------------------------------------------
def test_build_hourly_snapshot_drops_stale_fuel_prices():
    """
    A station that reports today but stopped posting a valid price for a
    specific fuel must not carry that fuel forward from previous days.
    Otherwise a diesel-only reporting station would keep an old E5 price in
    the national average.
    """
    hourly_changes = pl.DataFrame(
        {
            "date": [date(2024, 1, 1)] * 2,
            "hour": [8, 12],
            "station_uuid": ["s1", "s1"],
            "price_diesel": [1.50, 1.55],
            "price_e5": [None, None],
            "price_e10": [None, None],
        }
    )
    state = pl.DataFrame(
        {
            "station_uuid": ["s1"],
            "price_diesel": [1.45],
            "price_e5": [1.55],
            "price_e10": [1.50],
        }
    )
    snapshot = build_hourly_snapshot(hourly_changes, state)
    s1_snapshot = snapshot.filter(pl.col("station_uuid") == "s1")
    assert s1_snapshot["price_diesel"].drop_nulls().len() == 24
    assert s1_snapshot["price_e5"].drop_nulls().len() == 0
    assert s1_snapshot["price_e10"].drop_nulls().len() == 0


def test_build_hourly_snapshot_drops_stale_carry_forward_stations():
    """
    Stations that stopped reporting must not be carried forward with stale
    prices. If only s1 reports today, the snapshot should contain s1 only,
    even if the previous day's state still holds a price for s2.
    """
    hourly_changes = pl.DataFrame(
        {
            "date": [date(2024, 1, 1)],
            "hour": [12],
            "station_uuid": ["s1"],
            "price_diesel": [1.50],
            "price_e5": [1.60],
            "price_e10": [1.55],
        }
    )
    state = pl.DataFrame(
        {
            "station_uuid": ["s1", "s2"],
            "price_diesel": [1.45, 0.90],
            "price_e5": [1.55, 1.409],
            "price_e10": [1.50, 1.40],
        }
    )
    snapshot = build_hourly_snapshot(hourly_changes, state)
    assert snapshot["station_uuid"].unique().to_list() == ["s1"]


def test_build_hourly_snapshot_forward_fills_and_seeds_hour_zero():
    """
    The dashboard needs a complete 24-hour price path for every station, even
    when the raw file only contains the hours in which a price changed.
    build_hourly_snapshot() must (a) cross-join every known station with 24
    hours, (b) seed hour 0 from the previous day's carry-forward state, and
    (c) forward-fill unchanged hours.
    """
    hourly_changes = pl.DataFrame(
        {
            "date": [date(2024, 1, 1)] * 2,
            "hour": [10, 14],
            "station_uuid": ["s1", "s1"],
            "price_diesel": [1.50, 1.55],
            "price_e5": [1.60, 1.65],
            "price_e10": [1.55, 1.60],
        }
    )
    state = pl.DataFrame(
        {
            "station_uuid": ["s1"],
            "price_diesel": [1.45],
            "price_e5": [1.55],
            "price_e10": [1.50],
        }
    )
    snapshot = build_hourly_snapshot(hourly_changes, state)

    # 24 rows for the one station
    assert snapshot.height == 24

    # Hour 0 seeded from carry-forward state
    hour0 = snapshot.filter(pl.col("hour") == 0)
    assert hour0["price_diesel"][0] == pytest.approx(1.45)

    # Hour 10 has the explicit new price
    hour10 = snapshot.filter(pl.col("hour") == 10)
    assert hour10["price_diesel"][0] == pytest.approx(1.50)

    # Hour 11 forward-filled from hour 10
    hour11 = snapshot.filter(pl.col("hour") == 11)
    assert hour11["price_diesel"][0] == pytest.approx(1.50)

    # Hour 14 and onwards forward-filled from the second change
    hour15 = snapshot.filter(pl.col("hour") == 15)
    assert hour15["price_diesel"][0] == pytest.approx(1.55)


# ---------------------------------------------------------------------------
# 3. Change-frequency computation
# ---------------------------------------------------------------------------
def test_compute_daily_price_changes_counts_true_transitions():
    """
    The raw Tankerkönig *change columns are unreliable (overlapping imports can
    duplicate the same physical change). compute_daily_price_changes() recomputes
    transitions from the forward-filled hourly snapshot. This metric powers the
    brand price-change-frequency chart, so an off-by-one here would make brands
    look more or less active than they really are.
    """
    snapshot = pl.DataFrame(
        {
            "date": [date(2024, 1, 1)] * 5,
            "hour": [0, 1, 2, 3, 4],
            "station_uuid": ["s1"] * 5,
            "price_diesel": [1.40, 1.40, 1.45, 1.45, 1.45],
            "price_e5": [1.50, 1.55, 1.55, 1.60, 1.60],
            "price_e10": [1.45, 1.45, 1.45, 1.45, 1.45],
        }
    )
    changes = compute_daily_price_changes(snapshot)

    assert changes["changes_diesel"][0] == 1  # one transition at hour 2
    assert changes["changes_e5"][0] == 2      # transitions at hour 1 and hour 3
    assert changes["changes_e10"][0] == 0


# ---------------------------------------------------------------------------
# 4. National hourly / daily aggregation
# ---------------------------------------------------------------------------
def test_summarize_hourly_and_daily():
    """
    These two functions produce the national daily file that drives the Brent vs
    Pump chart and KPI cards. We verify that means are computed correctly across
    stations and that the daily reporting count is the max over hours.
    """
    snapshot = pl.DataFrame(
        {
            "date": [date(2024, 1, 1)] * 4,
            "hour": [0, 0, 1, 1],
            "station_uuid": ["s1", "s2", "s1", "s2"],
            "price_diesel": [1.40, 1.50, 1.42, 1.52],
            "price_e5": [1.50, 1.60, 1.52, 1.62],
            "price_e10": [1.45, 1.55, 1.47, 1.57],
        }
    )
    hourly = summarize_hourly(snapshot)
    assert hourly.height == 2
    hour0 = hourly.filter(pl.col("hour") == 0)
    assert hour0["price_diesel"][0] == pytest.approx(1.45)
    assert hour0["stations_reporting"][0] == 2

    daily = summarize_daily(hourly)
    assert daily.height == 1
    assert daily["price_diesel"][0] == pytest.approx(1.46)  # mean of 1.40,1.50,1.42,1.52
    assert daily["stations_reporting"][0] == 2  # max over hours


# ---------------------------------------------------------------------------
# 5. Brand aggregation and small-brand bucketing
# ---------------------------------------------------------------------------
def test_summarize_brand_daily_groups_small_brands():
    """
    The Brand Comparison tab intentionally groups brands below 50 stations into
    'Other brands (<50 stations)' to avoid noise from tiny operators. This test
    guards that rule and checks both the 'brand' and 'owner' analysis levels.
    """
    snapshot = pl.DataFrame(
        {
            "date": [date(2024, 1, 1)] * 4,
            "hour": [10] * 4,
            "station_uuid": ["s1", "s2", "s3", "s4"],
            "price_diesel": [1.40, 1.50, 1.60, 1.70],
            "price_e5": [1.50, 1.60, 1.70, 1.80],
            "price_e10": [1.45, 1.55, 1.65, 1.75],
        }
    )
    metadata = pl.DataFrame(
        {
            "station_uuid": ["s1", "s2", "s3", "s4"],
            "brand": ["BIG", "BIG", "SMALL", "SMALL"],
            "brand_group": ["BIG", "BIG", OTHER_BRAND_BUCKET, OTHER_BRAND_BUCKET],
            "corporate_group": ["BIG CORP", "BIG CORP", "INDIE", "INDIE"],
            "region": ["North"] * 4,
            "brand_station_count": [100, 100, 10, 10],
        }
    )
    brand_df = summarize_brand_daily(snapshot, metadata, daily_changes=None)

    # Should have 4 rows: BIG brand, Other brands bucket, BIG CORP owner, INDIE owner
    assert brand_df.height == 4

    brand_level = brand_df.filter(pl.col("analysis_level") == "brand")
    big = brand_level.filter(pl.col("comparison_group") == "BIG")
    other = brand_level.filter(pl.col("comparison_group") == OTHER_BRAND_BUCKET)
    assert big["price_e5"][0] == pytest.approx(1.55)
    assert other["price_e5"][0] == pytest.approx(1.75)


def test_summarize_brand_daily_returns_empty_schema_when_no_metadata():
    """
    If station metadata is missing, the pipeline should still write a brand file
    with the correct schema rather than crashing or producing a malformed
    parquet. This keeps downstream consumers robust.
    """
    snapshot = pl.DataFrame(
        {
            "date": [date(2024, 1, 1)],
            "hour": [10],
            "station_uuid": ["s1"],
            "price_diesel": [1.40],
            "price_e5": [1.50],
            "price_e10": [1.45],
        }
    )
    empty_meta = pl.DataFrame(
        schema={
            "station_uuid": pl.String,
            "brand": pl.String,
            "brand_group": pl.String,
            "corporate_group": pl.String,
            "region": pl.String,
            "brand_station_count": pl.UInt32,
        }
    )
    result = summarize_brand_daily(snapshot, empty_meta)
    assert result.is_empty()
    assert "analysis_level" in result.columns
    assert "comparison_group" in result.columns


# ---------------------------------------------------------------------------
# 6. Regional aggregation
# ---------------------------------------------------------------------------
def test_summarize_regional_daily():
    """
    The regional file is used both for the Regional Pricing tab and for the
    station-count-weighted national average in the dashboard. We verify that
    prices and station counts are aggregated by the region field.
    """
    snapshot = pl.DataFrame(
        {
            "date": [date(2024, 1, 1)] * 4,
            "hour": [10] * 4,
            "station_uuid": ["s1", "s2", "s3", "s4"],
            "price_diesel": [1.40, 1.50, 1.60, 1.70],
            "price_e5": [1.50, 1.60, 1.70, 1.80],
            "price_e10": [1.45, 1.55, 1.65, 1.75],
        }
    )
    metadata = pl.DataFrame(
        {
            "station_uuid": ["s1", "s2", "s3", "s4"],
            "brand": ["A", "A", "B", "B"],
            "brand_group": ["A", "A", "B", "B"],
            "corporate_group": ["X", "X", "Y", "Y"],
            "region": ["North", "North", "South", "South"],
            "brand_station_count": [1, 1, 1, 1],
        }
    )
    regional = summarize_regional_daily(snapshot, metadata)
    assert regional.height == 2

    north = regional.filter(pl.col("region") == "North")
    assert north["price_e5"][0] == pytest.approx(1.55)
    assert north["station_count"][0] == 2


# ---------------------------------------------------------------------------
# 7. Quality checks
# ---------------------------------------------------------------------------
def test_run_quality_checks_detects_gap_and_outlier():
    """
    _run_quality_checks() is the last line of defense before bad data reaches
    the dashboard. We verify it catches date gaps and prices outside the
    plausible [0.80, 3.00] EUR/L band.
    """
    daily = pl.DataFrame(
        {
            "date": [date(2024, 1, 1), date(2024, 1, 3), date(2024, 1, 4)],
            "price_diesel": [1.40, 5.00, 1.50],
            "price_e5": [1.50, 1.60, 1.70],
            "price_e10": [1.45, 1.55, 1.65],
        }
    )
    intraday = pl.DataFrame(
        {
            "date": [date(2024, 1, 1)] * 24,
            "hour": list(range(24)),
            "stations_reporting": [1000] * 24,
            "price_e5": [1.50] * 24,
        }
    )
    warnings = _run_quality_checks(daily, intraday)

    assert any("Missing" in w for w in warnings)
    assert any("outside" in w for w in warnings)


def test_run_quality_checks_passes_clean_data():
    """
    A clean, contiguous day with plausible prices and normal reporting should
    produce no warnings, avoiding false alarms during routine pipeline runs.
    """
    daily = pl.DataFrame(
        {
            "date": [date(2024, 1, 1), date(2024, 1, 2)],
            "price_diesel": [1.40, 1.41],
            "price_e5": [1.50, 1.51],
            "price_e10": [1.45, 1.46],
        }
    )
    intraday = pl.DataFrame(
        {
            "date": [date(2024, 1, 2)] * 24,
            "hour": list(range(24)),
            "stations_reporting": [1000] * 24,
            "price_e5": [1.51] * 24,
        }
    )
    warnings = _run_quality_checks(daily, intraday)
    assert warnings == []


# ---------------------------------------------------------------------------
# 8. Incremental-run validation
# ---------------------------------------------------------------------------
def test_validate_incremental_inputs_scenarios(tmp_path: Path):
    """
    _validate_incremental_inputs() prevents the pipeline from silently creating
    overlaps or gaps when new daily files are appended. We test the three
    possible states: continuous, overlap, and gap.
    """
    continuous = [tmp_path / "2024-01-02.parquet"]
    overlap = [tmp_path / "2024-01-01.parquet"]
    gap = [tmp_path / "2024-01-03.parquet"]
    for p in continuous + overlap + gap:
        p.touch()

    ok, msg = _validate_incremental_inputs(date(2024, 1, 1), continuous)
    assert ok is True
    assert "Continuous" in msg

    ok, msg = _validate_incremental_inputs(date(2024, 1, 1), overlap)
    assert ok is False
    assert "Overlap" in msg

    ok, msg = _validate_incremental_inputs(date(2024, 1, 1), gap)
    assert ok is False
    assert "Gap" in msg
