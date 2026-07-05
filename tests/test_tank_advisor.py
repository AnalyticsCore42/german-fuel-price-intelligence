"""
Test Suite: test_tank_advisor.py
Verifies the cost model, distance calculation, point-in-time data loading,
and recommendation logic for the Tank Advisor feature.
"""

import sys
from datetime import date, time, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import polars as pl
import pytest
import requests
from unittest.mock import MagicMock, patch

from gasprice.tank_advisor import (
    haversine_distance,
    estimate_driving_distance,
    compute_station_costs,
    find_best_station,
    load_advisor_data_for_datetime,
    list_available_price_dates,
    _compute_total_cost,
    geocode_address_suggestions,
    compute_savings_projection,
)


def test_haversine_distance_known_points():
    """Distance between Berlin and Munich should be roughly 505 km."""
    berlin = (52.520008, 13.404954)
    munich = (48.135125, 11.581981)
    dist = haversine_distance(*berlin, *munich)
    assert 500 < dist < 510


def test_estimate_driving_distance_applies_road_factor():
    assert estimate_driving_distance(10.0) == pytest.approx(13.0)


def _make_stations_df() -> pl.DataFrame:
    return pl.DataFrame({
        "station_uuid": ["s1", "s2", "s3"],
        "brand": ["CHEAP_FAR", "EXPENSIVE_CLOSE", "MID"],
        "name": ["Far Cheap", "Close Expensive", "Mid"],
        "street": ["A", "B", "C"],
        "house_number": ["1", "2", "3"],
        "post_code": ["10000", "10001", "10002"],
        "city": ["Berlin", "Berlin", "Berlin"],
        "latitude": [52.62, 52.52, 52.55],
        "longitude": [13.40, 13.40, 13.40],
        "price_e5": [1.50, 1.80, 1.70],
        "price_diesel": [1.40, 1.70, 1.60],
    })


def test_compute_station_costs_filters_by_radius():
    df = _make_stations_df()
    result = compute_station_costs(df, 52.52, 13.40, "e5", 50, 7, radius_km=5)
    # Only the close station (s2) and mid (s3) should be within 5 km.
    assert result.height == 2
    uuids = set(result["station_uuid"].to_list())
    assert uuids == {"s2", "s3"}


def test_compute_station_costs_sorts_by_total_cost():
    df = _make_stations_df()
    result = compute_station_costs(df, 52.52, 13.40, "e5", 50, 7, radius_km=50)
    # Far cheap station should still win because price difference dominates.
    assert result.row(0, named=True)["station_uuid"] == "s1"


def test_find_best_station_recommends_cheapest_and_expensive():
    df = _make_stations_df()
    result = find_best_station(df, 52.52, 13.40, "e5", 50, 7, radius_km=50)
    assert result["recommended"]["station_uuid"] == "s1"
    assert result["closest"]["station_uuid"] == "s2"
    # s2 is both closest and most expensive total cost in this fixture.
    assert result["expensive"]["station_uuid"] == "s2"
    assert result["savings_eur"] > 0


def test_find_best_station_no_savings_when_closest_is_cheapest():
    df = _make_stations_df().with_columns(
        pl.when(pl.col("station_uuid") == "s2")
        .then(1.40)
        .otherwise(pl.col("price_e5"))
        .alias("price_e5")
    )
    result = find_best_station(df, 52.52, 13.40, "e5", 50, 7, radius_km=50)
    assert result["recommended"]["station_uuid"] == "s2"
    assert result["closest"]["station_uuid"] == "s2"
    assert result["savings_eur"] == pytest.approx(0.0)


def test_compute_station_costs_raises_on_missing_fuel():
    df = _make_stations_df()
    with pytest.raises(ValueError, match="not available in price data"):
        compute_station_costs(df, 52.52, 13.40, "e100", 50, 7)


def test_geocode_address_suggestions_parses_photon_response():
    """
    geocode_address_suggestions() must parse a Photon (OSM) response and
    return human-readable labels plus coordinates.
    """
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "features": [
            {
                "properties": {
                    "name": "Kassel",
                    "street": "",
                    "housenumber": "",
                    "postcode": "",
                    "city": "Kassel",
                    "state": "Hessen",
                    "country": "Deutschland",
                },
                "geometry": {"coordinates": [9.4978479, 51.3157833]},
            }
        ]
    }

    with patch("gasprice.tank_advisor.requests.get", return_value=mock_response):
        suggestions = geocode_address_suggestions("kassel")

    assert len(suggestions) == 1
    assert suggestions[0]["label"] == "Kassel, Kassel, Hessen, Deutschland"
    assert suggestions[0]["lat"] == pytest.approx(51.3157833)
    assert suggestions[0]["lon"] == pytest.approx(9.4978479)


def test_geocode_address_suggestions_returns_empty_on_error():
    """Network or API errors should degrade gracefully to an empty list."""
    with patch("gasprice.tank_advisor.requests.get", side_effect=requests.RequestException("network down")):
        suggestions = geocode_address_suggestions("kassel")
    assert suggestions == []


def test_compute_total_cost_uses_round_trip():
    """
    A refuelling trip is a round trip. If we used one-way distance, the
    driving cost would be half the real value and far-away cheap stations
    would be over-recommended.
    """
    one_way = _compute_total_cost(1.50, 50.0, 10.0, 7.0)
    # 50*1.50 + 1.50 * (10*1.3*2 / 100) * 7
    expected = 75.0 + 1.50 * 0.26 * 7.0
    assert one_way == pytest.approx(expected)


def test_load_advisor_data_for_datetime_takes_last_observation_before_time(tmp_path: Path):
    """
    load_advisor_data_for_datetime() must return the last observation per
    station on the selected day that is not later than the selected time.
    """
    target_date = date(2026, 7, 3)
    prices_dir = tmp_path / "prices" / str(target_date.year)
    prices_dir.mkdir(parents=True)
    price_file = prices_dir / f"{target_date.isoformat()}.parquet"

    # Two observations for s1: one early, one late. Target time 12:00 should pick early.
    # s2 only has a late observation -> excluded.
    prices = pl.DataFrame({
        "date": [
            datetime(2026, 7, 3, 8, 0, 0, tzinfo=ZoneInfo("Europe/Berlin")),
            datetime(2026, 7, 3, 14, 0, 0, tzinfo=ZoneInfo("Europe/Berlin")),
            datetime(2026, 7, 3, 14, 0, 0, tzinfo=ZoneInfo("Europe/Berlin")),
        ],
        "station_uuid": ["s1", "s1", "s2"],
        "diesel": [1.50, 1.60, 1.70],
        "e5": [1.60, 1.70, 1.80],
        "e10": [1.55, 1.65, 1.75],
        "dieselchange": [0, 0, 0],
        "e5change": [0, 0, 0],
        "e10change": [0, 0, 0],
    })
    prices.write_parquet(price_file)

    stations = pl.DataFrame({
        "uuid": ["s1", "s2"],
        "brand": ["A", "B"],
        "name": ["A1", "B1"],
        "street": ["X", "Y"],
        "house_number": ["1", "2"],
        "post_code": ["10000", "10001"],
        "city": ["Berlin", "Berlin"],
        "latitude": [52.52, 52.53],
        "longitude": [13.40, 13.41],
    })
    stations_path = tmp_path / "stations.parquet"
    stations.write_parquet(stations_path)

    result = load_advisor_data_for_datetime(prices_dir.parent, stations_path, target_date, time(12, 0))
    assert result.height == 1
    row = result.row(0, named=True)
    assert row["station_uuid"] == "s1"
    assert row["price_e5"] == pytest.approx(1.60)


def test_load_advisor_data_for_datetime_filters_invalid_prices(tmp_path: Path):
    """Prices outside the valid range should be treated as null."""
    target_date = date(2026, 7, 3)
    prices_dir = tmp_path / "prices" / str(target_date.year)
    prices_dir.mkdir(parents=True)
    price_file = prices_dir / f"{target_date.isoformat()}.parquet"

    prices = pl.DataFrame({
        "date": [datetime(2026, 7, 3, 8, 0, 0, tzinfo=ZoneInfo("Europe/Berlin"))],
        "station_uuid": ["s1"],
        "diesel": [0.5],
        "e5": [5.0],
        "e10": [1.60],
        "dieselchange": [0],
        "e5change": [0],
        "e10change": [0],
    })
    prices.write_parquet(price_file)

    stations = pl.DataFrame({
        "uuid": ["s1"],
        "brand": ["A"],
        "name": ["A1"],
        "street": ["X"],
        "house_number": ["1"],
        "post_code": ["10000"],
        "city": ["Berlin"],
        "latitude": [52.52],
        "longitude": [13.40],
    })
    stations_path = tmp_path / "stations.parquet"
    stations.write_parquet(stations_path)

    result = load_advisor_data_for_datetime(prices_dir.parent, stations_path, target_date, time(23, 0))
    assert result.height == 1
    row = result.row(0, named=True)
    assert row["price_diesel"] is None
    assert row["price_e5"] is None
    assert row["price_e10"] == pytest.approx(1.60)


def test_list_available_price_dates(tmp_path: Path):
    prices_dir = tmp_path / "prices"
    (prices_dir / "2026").mkdir(parents=True)
    (prices_dir / "2026" / "2026-07-01.parquet").write_text("")
    (prices_dir / "2026" / "2026-07-02.parquet").write_text("")
    dates = list_available_price_dates(prices_dir)
    assert dates == [date(2026, 7, 1), date(2026, 7, 2)]


def test_compute_savings_projection_scales_to_month_and_year():
    # 50 L tank, 7 L/100km, 1200 km/month -> 14400 km/year -> 1008 L/year -> ~20 refuels
    proj = compute_savings_projection(100.0, 50.0, 1200.0, 7.0)
    assert proj["refuels_per_year"] == pytest.approx(20.16, rel=1e-3)
    assert proj["annual_cost"] == pytest.approx(2016.0, rel=1e-3)
    assert proj["monthly_cost"] == pytest.approx(168.0, rel=1e-3)
