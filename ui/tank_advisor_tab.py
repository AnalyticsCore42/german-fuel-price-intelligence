"""
Tank Advisor tab content for the Streamlit dashboard.
"""

from __future__ import annotations

import streamlit as st
import polars as pl
from datetime import datetime, time, date
from pathlib import Path

from gasprice.tank_advisor import (
    list_available_price_dates,
    load_advisor_data_for_datetime,
    geocode_address,
    geocode_address_suggestions,
    find_best_station,
    build_folium_map,
    compute_savings_projection,
    DEFAULT_KM_PER_MONTH,
)


def _init_session_state(default_lat: float, default_lon: float, default_date: date) -> None:
    """Ensure Tank Advisor session-state keys exist."""
    defaults = {
        "advisor_lat": default_lat,
        "advisor_lon": default_lon,
        "advisor_address": "",
        "advisor_suggestions": [],
        "advisor_request_location": False,
        "advisor_target_date": default_date,
        "advisor_target_time": time(12, 0),
        "advisor_km_per_month": DEFAULT_KM_PER_MONTH,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def render_tank_advisor_tab(
    data_dir: Path,
    fuel_key: str,
    translate: callable,
) -> None:
    st.markdown(f"#### {translate('advisor_title')}")
    st.markdown(f"<span style='color:#8892A4;font-size:0.85rem;'>{translate('advisor_note')}</span>", unsafe_allow_html=True)

    # Resolve paths
    prices_dir = data_dir / "tankerkoenig" / "prices"
    stations_path = data_dir / "tankerkoenig" / "stations" / "cleaned-stations.parquet"

    if not prices_dir.exists() or not stations_path.exists():
        st.warning(translate("advisor_data_missing"))
        return

    available_dates = list_available_price_dates(prices_dir)
    if not available_dates:
        st.warning(translate("advisor_data_missing"))
        return

    DEFAULT_LAT, DEFAULT_LON = 52.520008, 13.404954
    _init_session_state(DEFAULT_LAT, DEFAULT_LON, available_dates[-1])

    # ── Inputs ──
    c_loc, c_vehicle = st.columns([2, 1])

    with c_loc:
        st.markdown(f"**{translate('advisor_location')}**")

        # Browser geolocation: use streamlit-js-eval component only after the
        # user explicitly clicks the button. This avoids permission prompts on
        # every page load and works inside Streamlit's component iframe.
        if st.button(translate("advisor_use_location"), use_container_width=True):
            st.session_state["advisor_request_location"] = True

        if st.session_state.get("advisor_request_location") is True:
            # Lazy import: streamlit_js_eval needs streamlit.components.v1, which
            # is not available in the headless test environment.
            from streamlit_js_eval import get_geolocation
            loc = get_geolocation(component_key="tank_advisor_geolocation")
            if loc is not None:
                if "error" in loc:
                    st.error(translate("advisor_location_failed"))
                    st.session_state["advisor_request_location"] = False
                elif "coords" in loc:
                    st.session_state["advisor_lat"] = float(loc["coords"]["latitude"])
                    st.session_state["advisor_lon"] = float(loc["coords"]["longitude"])
                    st.session_state["advisor_request_location"] = False
                    st.rerun()

        # Address autocomplete via Photon (OSM).
        # We use the returned value directly and keep a separate canonical key,
        # because Streamlit does not allow writing to a widget's own session_state
        # key after the widget has been instantiated.
        address_value = st.text_input(
            translate("advisor_address"),
            placeholder=translate("advisor_address_placeholder"),
            value=st.session_state.get("advisor_address", ""),
        )
        # Sync the canonical address value (not a widget key) so selections and
        # reruns can update the input without hitting Streamlit's restriction.
        st.session_state["advisor_address"] = address_value

        # Live-suggest as soon as the user has typed at least 3 characters.
        # Photon is free, so we keep it simple and rely on the user's input
        # changing; the last queried string avoids duplicate calls on reruns.
        if isinstance(address_value, str):
            query = address_value.strip()
            last_query = st.session_state.get("advisor_last_query", "")
            if len(query) >= 3 and query != last_query:
                with st.spinner("Searching…"):
                    st.session_state["advisor_suggestions"] = geocode_address_suggestions(query)
                    st.session_state["advisor_last_query"] = query
            elif len(query) < 3:
                st.session_state["advisor_suggestions"] = []
                st.session_state["advisor_last_query"] = ""

        c_clear = st.columns([1])[0]
        with c_clear:
            if st.button(translate("advisor_clear_suggestions"), use_container_width=True):
                st.session_state["advisor_suggestions"] = []
                st.session_state["advisor_last_query"] = st.session_state.get("advisor_address", "")

        suggestions = st.session_state.get("advisor_suggestions", [])
        if isinstance(suggestions, list) and suggestions:
            labels = [s["label"] for s in suggestions]
            selected_label = st.selectbox(
                translate("advisor_suggestions"),
                options=labels,
                index=None,
                placeholder=translate("advisor_pick_suggestion"),
            )
            if selected_label:
                selected = next((s for s in suggestions if s["label"] == selected_label), None)
                if selected is not None:
                    st.session_state["advisor_lat"] = selected["lat"]
                    st.session_state["advisor_lon"] = selected["lon"]
                    st.session_state["advisor_address"] = selected_label
                    st.session_state["advisor_suggestions"] = []
                    st.rerun()

        c_lat, c_lon = st.columns(2)
        with c_lat:
            st.number_input(
                "Lat",
                value=st.session_state["advisor_lat"],
                format="%.6f",
                label_visibility="collapsed",
                key="advisor_lat",
            )
        with c_lon:
            st.number_input(
                "Lon",
                value=st.session_state["advisor_lon"],
                format="%.6f",
                label_visibility="collapsed",
                key="advisor_lon",
            )

        # Date / time of the historical price snapshot.
        st.markdown(f"**{translate('advisor_snapshot_time')}**")
        c_date, c_time = st.columns(2)
        with c_date:
            st.date_input(
                translate("advisor_date"),
                value=st.session_state["advisor_target_date"],
                min_value=available_dates[0],
                max_value=available_dates[-1],
                key="advisor_target_date",
            )
        with c_time:
            st.time_input(
                translate("advisor_time"),
                value=st.session_state["advisor_target_time"],
                key="advisor_target_time",
            )

    with c_vehicle:
        st.markdown(f"**{translate('advisor_vehicle')}**")
        tank_size = st.number_input(
            translate("advisor_tank_size"),
            min_value=1.0,
            max_value=200.0,
            value=50.0,
            step=5.0,
        )
        consumption = st.number_input(
            translate("advisor_consumption"),
            min_value=1.0,
            max_value=30.0,
            value=7.0,
            step=0.5,
        )
        radius = st.slider(
            translate("advisor_radius"),
            min_value=1,
            max_value=50,
            value=20,
        )
        st.number_input(
            translate("advisor_km_per_month"),
            min_value=1.0,
            max_value=10000.0,
            value=st.session_state["advisor_km_per_month"],
            step=100.0,
            key="advisor_km_per_month",
        )

    # ── Compute recommendation ──
    if st.button(translate("advisor_calculate"), type="primary", use_container_width=True):
        with st.spinner("Calculating… / Berechne…"):
            advisor_df = load_advisor_data_for_datetime(
                prices_dir,
                stations_path,
                st.session_state["advisor_target_date"],
                st.session_state["advisor_target_time"],
            )

            if advisor_df.is_empty():
                st.error(translate("advisor_no_data_for_date"))
                return

            result = find_best_station(
                advisor_df,
                st.session_state["advisor_lat"],
                st.session_state["advisor_lon"],
                fuel_key,
                tank_size,
                consumption,
                radius_km=float(radius),
            )

        if result["recommended"] is None:
            st.error(translate("advisor_no_stations"))
            return

        rec = result["recommended"]
        closest = result["closest"]
        expensive = result["expensive"]
        savings = result["savings_eur"]

        # ── KPI cards ──
        st.markdown("---")
        c_rec, c_closest, c_expensive, c_save = st.columns(4)

        address_rec = f"{rec.get('street', '')} {rec.get('house_number', '')}, {rec.get('post_code', '')} {rec.get('city', '')}".strip(", ")
        address_closest = f"{closest.get('street', '')} {closest.get('house_number', '')}, {closest.get('post_code', '')} {closest.get('city', '')}".strip(", ")
        address_expensive = f"{expensive.get('street', '')} {expensive.get('house_number', '')}, {expensive.get('post_code', '')} {expensive.get('city', '')}".strip(", ")

        with c_rec:
            st.markdown(
                f"""
                <div class="kpi-card insight">
                    <div class="kpi-label">{translate('advisor_recommended')}</div>
                    <div class="kpi-value">{rec.get('brand', 'Unknown')}</div>
                    <div class="kpi-subtitle">€{rec['fuel_price']:.3f}/L · {rec['road_distance_km']:.1f} km one-way</div>
                    <div class="kpi-subtitle">Fuel €{rec['fuel_price'] * tank_size:.2f} + driving €{rec['driving_cost']:.2f} = total €{rec['total_cost']:.2f}</div>
                    <div class="kpi-subtitle">{address_rec}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with c_closest:
            st.markdown(
                f"""
                <div class="kpi-card">
                    <div class="kpi-label">{translate('advisor_closest')}</div>
                    <div class="kpi-value">{closest.get('brand', 'Unknown')}</div>
                    <div class="kpi-subtitle">€{closest['fuel_price']:.3f}/L · {closest['road_distance_km']:.1f} km one-way</div>
                    <div class="kpi-subtitle">Fuel €{closest['fuel_price'] * tank_size:.2f} + driving €{closest['driving_cost']:.2f} = total €{closest['total_cost']:.2f}</div>
                    <div class="kpi-subtitle">{address_closest}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with c_expensive:
            st.markdown(
                f"""
                <div class="kpi-card">
                    <div class="kpi-label">{translate('advisor_expensive')}</div>
                    <div class="kpi-value">{expensive.get('brand', 'Unknown')}</div>
                    <div class="kpi-subtitle">€{expensive['fuel_price']:.3f}/L · {expensive['road_distance_km']:.1f} km one-way</div>
                    <div class="kpi-subtitle">Total €{expensive['total_cost']:.2f}</div>
                    <div class="kpi-subtitle">{address_expensive}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with c_save:
            save_color = "down" if savings > 0 else "up"
            st.markdown(
                f"""
                <div class="kpi-card">
                    <div class="kpi-label">{translate('advisor_savings')}</div>
                    <div class="kpi-value">€{savings:.2f}</div>
                    <div class="kpi-subtitle">{translate('advisor_per_tank')}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # ── Recommendation text ──
        st.markdown("---")
        if savings <= 0.01:
            st.success(translate("advisor_closest_is_best"))
        else:
            st.success(
                translate("advisor_recommendation_text").format(
                    brand=rec.get('brand', 'Unknown'),
                    price=rec['fuel_price'],
                    distance=rec['road_distance_km'],
                    savings=savings,
                )
            )

        # ── Annual savings projection ──
        st.markdown(f"#### {translate('advisor_savings_projection')}")
        st.markdown(f"<span style='color:#8892A4;font-size:0.85rem;'>{translate('advisor_savings_projection_note')}</span>", unsafe_allow_html=True)

        km_per_month = st.session_state["advisor_km_per_month"]
        rec_proj = compute_savings_projection(rec["total_cost"], tank_size, km_per_month, consumption)
        closest_proj = compute_savings_projection(closest["total_cost"], tank_size, km_per_month, consumption)
        expensive_proj = compute_savings_projection(expensive["total_cost"], tank_size, km_per_month, consumption)

        c_month, c_year = st.columns(2)
        with c_month:
            monthly_savings_vs_closest = closest_proj["monthly_cost"] - rec_proj["monthly_cost"]
            monthly_savings_vs_expensive = expensive_proj["monthly_cost"] - rec_proj["monthly_cost"]
            st.markdown(
                f"""
                <div class="kpi-card">
                    <div class="kpi-label">{translate('advisor_monthly_savings')}</div>
                    <div class="kpi-value">€{monthly_savings_vs_closest:.2f}</div>
                    <div class="kpi-subtitle">vs. closest station</div>
                    <div class="kpi-subtitle">€{monthly_savings_vs_expensive:.2f} vs. most expensive</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with c_year:
            annual_savings_vs_closest = closest_proj["annual_cost"] - rec_proj["annual_cost"]
            annual_savings_vs_expensive = expensive_proj["annual_cost"] - rec_proj["annual_cost"]
            st.markdown(
                f"""
                <div class="kpi-card">
                    <div class="kpi-label">{translate('advisor_annual_savings')}</div>
                    <div class="kpi-value">€{annual_savings_vs_closest:.2f}</div>
                    <div class="kpi-subtitle">vs. closest station</div>
                    <div class="kpi-subtitle">€{annual_savings_vs_expensive:.2f} vs. most expensive</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # ── Map ──
        from streamlit_folium import st_folium
        folium_map = build_folium_map(
            st.session_state["advisor_lat"],
            st.session_state["advisor_lon"],
            result["all_stations"],
            rec,
            closest,
            expensive,
        )
        st_folium(folium_map, width=1200, height=500, returned_objects=[])

        # ── Top stations table ──
        st.markdown(f"**{translate('advisor_top_stations')}**")
        top = (
            result["all_stations"]
            .head(10)
            .select([
                "brand",
                "name",
                "street",
                "house_number",
                "post_code",
                "city",
                "fuel_price",
                "distance_km",
                "road_distance_km",
                "driving_cost",
                "total_cost",
            ])
            .to_pandas()
        )
        top["fuel_price"] = top["fuel_price"].apply(lambda x: f"€{x:.3f}/L")
        top["distance_km"] = top["distance_km"].apply(lambda x: f"{x:.1f} km")
        top["road_distance_km"] = top["road_distance_km"].apply(lambda x: f"{x:.1f} km")
        top["driving_cost"] = top["driving_cost"].apply(lambda x: f"€{x:.2f}")
        top["total_cost"] = top["total_cost"].apply(lambda x: f"€{x:.2f}")
        st.dataframe(top, hide_index=True, use_container_width=True)
