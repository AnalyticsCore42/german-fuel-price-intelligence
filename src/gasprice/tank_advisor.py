"""
Module: tank_advisor.py
Description: Core logic for the Tank Advisor dashboard feature.
             Helps users find the cheapest refuelling option when driving
             cost is taken into account. Uses historical point-in-time price
             data so the user can answer: "On date X at time Y, where should
             I have refuelled?"
"""

from __future__ import annotations

import math
from datetime import date, datetime, time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import polars as pl
import requests
from geopy.exc import GeocoderTimedOut
from geopy.geocoders import Nominatim

EARTH_RADIUS_KM = 6371.0
ROAD_FACTOR = 1.3  # rough multiplier to convert straight-line to road distance
DEFAULT_RADIUS_KM = 20.0
MIN_PRICE_VALID = 0.80
MAX_PRICE_VALID = 3.00
DEFAULT_KM_PER_MONTH = 1200.0


def list_available_price_dates(prices_dir: Path) -> list[date]:
    """Return all dates for which a daily price parquet file exists."""
    files = sorted(prices_dir.rglob("*.parquet"))
    dates: list[date] = []
    for f in files:
        try:
            dates.append(date.fromisoformat(f.stem))
        except ValueError:
            continue
    return dates


def load_advisor_data_for_datetime(
    prices_dir: Path,
    stations_path: Path,
    target_date: date,
    target_time: time,
) -> pl.DataFrame:
    """
    Load station prices for a specific date and time, joined with metadata.

    For each station we take the last observed price on `target_date` that is
    not later than `target_time` (Europe/Berlin). Stations without any valid
    observation on that day are excluded. This gives a true point-in-time
    snapshot instead of a stale carry-forward price or a smoothed average.

    Returns a Polars DataFrame with one row per station that has both a
    known price and known coordinates.
    """
    price_file = prices_dir / f"{target_date.year}" / f"{target_date.isoformat()}.parquet"
    if not price_file.exists():
        return pl.DataFrame()

    stations = pl.read_parquet(stations_path)
    uuid_col = "uuid" if "uuid" in stations.columns else "station_uuid"

    metadata = stations.select([
        pl.col(uuid_col).cast(pl.String).alias("station_uuid"),
        pl.col("brand").fill_null("UNKNOWN").str.strip_chars().str.to_uppercase().alias("brand"),
        pl.col("name").fill_null("").alias("name"),
        pl.col("street").fill_null("").alias("street"),
        pl.col("house_number").fill_null("").alias("house_number"),
        pl.col("post_code").fill_null("").alias("post_code"),
        pl.col("city").fill_null("").alias("city"),
        pl.col("latitude").cast(pl.Float64).alias("latitude"),
        pl.col("longitude").cast(pl.Float64).alias("longitude"),
    ])

    target_dt = datetime(
        target_date.year,
        target_date.month,
        target_date.day,
        target_time.hour,
        target_time.minute,
        tzinfo=ZoneInfo("Europe/Berlin"),
    )

    raw = pl.read_parquet(price_file)
    raw = raw.with_columns(
        pl.col("date").dt.convert_time_zone("Europe/Berlin").alias("local_time")
    )

    # Only observations up to the requested time on that day.
    raw = raw.filter(pl.col("local_time") <= target_dt)
    if raw.is_empty():
        return pl.DataFrame()

    # Last observation per station up to the target time.
    latest = raw.sort(["station_uuid", "local_time"]).group_by("station_uuid").last()

    # Apply the same validity range used by the pipeline.
    latest = latest.with_columns([
        pl.when((pl.col("diesel") > MIN_PRICE_VALID) & (pl.col("diesel") < MAX_PRICE_VALID))
        .then(pl.col("diesel"))
        .otherwise(None)
        .alias("price_diesel"),
        pl.when((pl.col("e5") > MIN_PRICE_VALID) & (pl.col("e5") < MAX_PRICE_VALID))
        .then(pl.col("e5"))
        .otherwise(None)
        .alias("price_e5"),
        pl.when((pl.col("e10") > MIN_PRICE_VALID) & (pl.col("e10") < MAX_PRICE_VALID))
        .then(pl.col("e10"))
        .otherwise(None)
        .alias("price_e10"),
    ])

    return (
        latest.join(metadata, on="station_uuid", how="inner")
        .filter(
            pl.col("latitude").is_not_null()
            & pl.col("longitude").is_not_null()
            & (pl.col("latitude") != 0.0)
            & (pl.col("longitude") != 0.0)
        )
    )


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return the great-circle distance between two points in kilometers."""
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_KM * c


def estimate_driving_distance(straight_line_km: float, road_factor: float = ROAD_FACTOR) -> float:
    """Convert straight-line distance to an approximate road distance."""
    return straight_line_km * road_factor


def geocode_address(address: str, user_agent: str = "german-gasprice-advisor") -> tuple[float, float] | None:
    """
    Geocode a free-text address/zip/city to (lat, lon) using Nominatim.
    Returns None if the lookup fails or times out.
    """
    if not address or not address.strip():
        return None

    geolocator = Nominatim(user_agent=user_agent)
    try:
        location = geolocator.geocode(address, timeout=10)
    except GeocoderTimedOut:
        return None

    if location is None:
        return None

    return (float(location.latitude), float(location.longitude))


def geocode_address_suggestions(
    query: str,
    limit: int = 5,
    user_agent: str = "german-gasprice-advisor/1.0",
) -> list[dict[str, Any]]:
    """
    Fetch address autocomplete suggestions from Photon (OSM-based).

    Returns a list of dicts with keys:
        label: human-readable label
        lat, lon: WGS84 coordinates
        name, street, housenumber, postcode, city, state, country
    """
    if not query or not query.strip() or len(query.strip()) < 2:
        return []

    try:
        response = requests.get(
            "https://photon.komoot.io/api/",
            params={
                "q": query.strip(),
                "limit": limit,
                "lang": "de",
            },
            headers={"User-Agent": user_agent},
            timeout=10,
        )
        response.raise_for_status()
    except requests.RequestException:
        return []

    try:
        data = response.json()
    except ValueError:
        return []

    suggestions: list[dict[str, Any]] = []
    for feature in data.get("features", []):
        props = feature.get("properties", {})
        geom = feature.get("geometry", {})
        coords = geom.get("coordinates", [None, None])
        if coords[0] is None or coords[1] is None:
            continue

        # Photon returns [lon, lat]
        lon, lat = coords[0], coords[1]

        name = props.get("name", "")
        street = props.get("street", "")
        housenumber = props.get("housenumber", "")
        postcode = props.get("postcode", "")
        city = props.get("city", "") or props.get("town", "") or props.get("village", "")
        state = props.get("state", "")
        country = props.get("country", "")

        parts = [p for p in [name, f"{street} {housenumber}".strip(), postcode, city, state, country] if p]
        label = ", ".join(parts)

        suggestions.append({
            "label": label,
            "lat": float(lat),
            "lon": float(lon),
            "name": name,
            "street": street,
            "housenumber": housenumber,
            "postcode": postcode,
            "city": city,
            "state": state,
            "country": country,
        })

    return suggestions


def _compute_total_cost(
    fuel_price: float,
    tank_l: float,
    straight_distance_km: float,
    consumption_l_per_100km: float,
) -> float:
    """
    Compute total cost of refuelling at a station.

    Includes both the fuel actually bought and the fuel burned to drive
    there and back (round trip). Using a one-way distance here would
    understate the true cost and produce misleadingly optimistic savings
    for far-away stations.
    """
    fuel_cost = fuel_price * tank_l
    one_way_road_distance = estimate_driving_distance(straight_distance_km)
    round_trip_road_distance = one_way_road_distance * 2.0
    driving_cost = fuel_price * (round_trip_road_distance / 100.0) * consumption_l_per_100km
    return fuel_cost + driving_cost


def compute_station_costs(
    stations_df: pl.DataFrame,
    user_lat: float,
    user_lon: float,
    fuel_key: str,
    tank_l: float,
    consumption_l_per_100km: float,
    radius_km: float = DEFAULT_RADIUS_KM,
) -> pl.DataFrame:
    """
    Add distance, road distance, and total-cost columns to the station DataFrame
    and filter to stations within the search radius.
    """
    price_col = f"price_{fuel_key}"
    if price_col not in stations_df.columns:
        raise ValueError(f"Fuel type '{fuel_key}' not available in price data")

    df = stations_df.filter(pl.col(price_col).is_not_null() & (pl.col(price_col) > 0))

    # Vectorised haversine distance with numpy.
    lat_rad = np.radians(df["latitude"].to_numpy())
    lon_rad = np.radians(df["longitude"].to_numpy())
    user_lat_rad = math.radians(user_lat)
    user_lon_rad = math.radians(user_lon)

    dlat = lat_rad - user_lat_rad
    dlon = lon_rad - user_lon_rad
    a = (
        np.sin(dlat / 2.0) ** 2
        + np.cos(user_lat_rad) * np.cos(lat_rad) * np.sin(dlon / 2.0) ** 2
    )
    distances = EARTH_RADIUS_KM * 2.0 * np.arctan2(np.sqrt(a), np.sqrt(1.0 - a))

    df = df.with_columns([
        pl.Series("distance_km", distances, dtype=pl.Float64),
        pl.col(price_col).alias("fuel_price"),
    ])

    df = df.with_columns([
        (pl.col("distance_km") * ROAD_FACTOR).alias("road_distance_km"),
    ])

    df = df.filter(pl.col("distance_km") <= radius_km)

    # Vectorised total cost.  Multiply by 2 because a refuelling trip is a
    # round trip: drive to the station and back.
    price_np = df["fuel_price"].to_numpy()
    dist_np = df["distance_km"].to_numpy()
    fuel_cost_np = price_np * tank_l
    driving_cost_np = (
        price_np * (dist_np * ROAD_FACTOR * 2.0 / 100.0) * consumption_l_per_100km
    )
    total_cost_np = fuel_cost_np + driving_cost_np

    df = df.with_columns(pl.Series("total_cost", total_cost_np, dtype=pl.Float64))
    df = df.with_columns(pl.Series("driving_cost", driving_cost_np, dtype=pl.Float64))

    return df.sort("total_cost")


def find_best_station(
    stations_df: pl.DataFrame,
    user_lat: float,
    user_lon: float,
    fuel_key: str,
    tank_l: float,
    consumption_l_per_100km: float,
    radius_km: float = DEFAULT_RADIUS_KM,
) -> dict[str, Any]:
    """
    Find the cheapest total-cost station and the geographically closest station.

    Returns a dict with:
      - recommended: row of cheapest total-cost station
      - closest: row of closest station
      - expensive: row of most expensive total-cost station
      - savings_eur: cost difference between closest and recommended
      - all_stations: filtered DataFrame sorted by total cost
    """
    candidates = compute_station_costs(
        stations_df, user_lat, user_lon, fuel_key, tank_l, consumption_l_per_100km, radius_km
    )

    if candidates.is_empty():
        return {
            "recommended": None,
            "closest": None,
            "expensive": None,
            "savings_eur": 0.0,
            "all_stations": candidates,
        }

    recommended = candidates.row(0, named=True)
    closest = candidates.sort("distance_km").row(0, named=True)
    expensive = candidates.sort("total_cost", descending=True).row(0, named=True)
    savings_eur = closest["total_cost"] - recommended["total_cost"]

    return {
        "recommended": recommended,
        "closest": closest,
        "expensive": expensive,
        "savings_eur": max(0.0, savings_eur),
        "all_stations": candidates,
    }


def compute_savings_projection(
    total_cost: float,
    tank_l: float,
    km_per_month: float,
    consumption_l_per_100km: float,
) -> dict[str, float]:
    """
    Project a single-refuel total cost into monthly and annual cost/savings.

    Assumes the user drives `km_per_month` km every month and refuels a full
    tank each time. Returns annual and monthly cost/savings deltas relative to
    a baseline total cost of zero (callers should compute the difference
    between two stations).
    """
    if total_cost <= 0 or tank_l <= 0 or consumption_l_per_100km <= 0 or km_per_month <= 0:
        return {
            "refuels_per_year": 0.0,
            "annual_cost": 0.0,
            "monthly_cost": 0.0,
        }

    km_per_year = km_per_month * 12.0
    liters_per_year = km_per_year / 100.0 * consumption_l_per_100km
    refuels_per_year = liters_per_year / tank_l
    annual_cost = total_cost * refuels_per_year
    monthly_cost = annual_cost / 12.0

    return {
        "refuels_per_year": refuels_per_year,
        "annual_cost": annual_cost,
        "monthly_cost": monthly_cost,
    }


def build_folium_map(
    user_lat: float,
    user_lon: float,
    all_stations: pl.DataFrame,
    recommended: dict[str, Any] | None,
    closest: dict[str, Any] | None,
    expensive: dict[str, Any] | None,
) -> "folium.Map":
    """Build an interactive Folium map showing user, recommended, closest and expensive stations."""
    import folium

    m = folium.Map(
        location=[user_lat, user_lon],
        zoom_start=12,
        tiles="CartoDB dark_matter",
    )

    folium.Marker(
        [user_lat, user_lon],
        tooltip="Your location",
        icon=folium.Icon(color="blue", icon="user", prefix="fa"),
    ).add_to(m)

    if recommended is not None:
        folium.Marker(
            [recommended["latitude"], recommended["longitude"]],
            tooltip=f"Recommended: {recommended.get('brand', '')} — €{recommended['fuel_price']:.3f}/L",
            icon=folium.Icon(color="green", icon="gas-pump", prefix="fa"),
        ).add_to(m)
        folium.PolyLine(
            locations=[(user_lat, user_lon), (recommended["latitude"], recommended["longitude"])],
            color="green",
            weight=3,
            dash_array="10, 10",
        ).add_to(m)

    if closest is not None and (recommended is None or closest["station_uuid"] != recommended["station_uuid"]):
        folium.Marker(
            [closest["latitude"], closest["longitude"]],
            tooltip=f"Closest: {closest.get('brand', '')} — €{closest['fuel_price']:.3f}/L",
            icon=folium.Icon(color="orange", icon="location-dot", prefix="fa"),
        ).add_to(m)
        folium.PolyLine(
            locations=[(user_lat, user_lon), (closest["latitude"], closest["longitude"])],
            color="orange",
            weight=2,
        ).add_to(m)

    if expensive is not None and (
        recommended is None or expensive["station_uuid"] != recommended["station_uuid"]
    ) and (closest is None or expensive["station_uuid"] != closest["station_uuid"]):
        folium.Marker(
            [expensive["latitude"], expensive["longitude"]],
            tooltip=f"Most expensive: {expensive.get('brand', '')} — €{expensive['fuel_price']:.3f}/L",
            icon=folium.Icon(color="red", icon="arrow-trend-up", prefix="fa"),
        ).add_to(m)

    # Add a light circle for the search radius
    folium.Circle(
        [user_lat, user_lon],
        radius=DEFAULT_RADIUS_KM * 1000,
        color="blue",
        fill=True,
        fill_opacity=0.05,
    ).add_to(m)

    return m
