"""
Unit tests for compliance forensics engine (src/gasprice/compliance_forensics.py).
"""

from datetime import datetime
import polars as pl
import pytest
from src.gasprice.compliance_forensics import get_station_price_history


def test_empty_station():
    res = get_station_price_history("00000000-0000-0000-0000-000000000000", "e5")
    assert isinstance(res, pl.DataFrame)
    assert res.height == 0


def test_known_top_offender_scan():
    # ESSO station in Oberzent (Erbacher Str.)
    uuid = "ef31f531-ef1b-4845-b23f-f315e2b773e1"
    df = get_station_price_history(uuid, "e5")
    assert isinstance(df, pl.DataFrame)
    assert df.height > 1000
    assert "event_type" in df.columns
    assert "diff_ct" in df.columns
    assert "status_label" in df.columns
    assert "prev_price" in df.columns

    # Verify presence of allowed cuts, allowed noon hikes, and illegal hikes
    event_types = df["event_type"].unique().to_list()
    assert "allowed_cut" in event_types
    assert "allowed_noon" in event_types
    assert any(t.startswith("illegal") for t in event_types)

    # Check that diff_ct matches (price - prev_price) * 100
    sample = df.head(10)
    for row in sample.iter_rows(named=True):
        expected_diff_ct = round((row["price"] - row["prev_price"]) * 100, 2)
        assert abs(row["diff_ct"] - expected_diff_ct) < 0.05


def test_strict_noon_mode():
    uuid = "ef31f531-ef1b-4845-b23f-f315e2b773e1"
    df_cons = get_station_price_history(uuid, "e5", strict_noon=False)
    df_strict = get_station_price_history(uuid, "e5", strict_noon=True)

    illegals_cons = df_cons.filter(pl.col("event_type").str.starts_with("illegal")).height
    illegals_strict = df_strict.filter(pl.col("event_type").str.starts_with("illegal")).height

    # Strict mode (cutoff 12:05 instead of 13:00) detects significantly more violations
    assert illegals_strict > illegals_cons


def test_price_chain_and_noon_context():
    uuid = "ef31f531-ef1b-4845-b23f-f315e2b773e1"
    df = get_station_price_history(uuid, "e5", strict_noon=False)
    assert "chain_verified" in df.columns
    assert "noon_hike_time" in df.columns
    assert "noon_hike_ct" in df.columns
    assert "daily_hike_nr" in df.columns

    # 100% of price steps must satisfy (prev_price + diff == price)
    assert df["chain_verified"].all()

    # Any hike with daily_hike_nr >= 2 on a day with noon hike has valid noon context
    multi_hikes = df.filter(pl.col("daily_hike_nr") >= 2)
    assert multi_hikes.height > 0
    sample = multi_hikes.row(0, named=True)
    assert sample["noon_hike_time"] != "—"
    assert sample["noon_hike_ct"] > 0


