"""
Module: 04_app.py
Description: Premium Streamlit dashboard for German Gasoline Prices Analysis.
             Loads aggregated datasets from data/ and renders interactive tabs.
Inputs:  data/processed_daily_margins.parquet
         data/processed_intraday.parquet
         data/processed_brand_daily_margins.parquet
         data/processed_regional_daily_margins.parquet
Outputs: Interactive dark-mode dashboard on http://localhost:8501
"""

import streamlit as st
import polars as pl
import plotly.graph_objects as go
import os
import json
from math import erfc, sqrt
from datetime import date, timedelta
from pathlib import Path

# Resolve data path relative to this script file — works from any working directory
DATA_DIR = Path(__file__).parent.parent / "data"
INTRADAY_FILE = DATA_DIR / "processed_intraday.parquet"
BRAND_DAILY_FILE = DATA_DIR / "processed_brand_daily_margins.parquet"
REGIONAL_DAILY_FILE = DATA_DIR / "processed_regional_daily_margins.parquet"

# ==========================================
# 1. SETUP & CONFIGURATION
# ==========================================

st.set_page_config(
    page_title="Tankpreise — Fuel Price Analysis / Deutsche Kraftstoffpreise",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={"About": "German Fuel Price Spread Analysis — Phase 4 Dashboard / Deutsche Kraftstoffpreis-Spannenanalyse"}
)

# ---- CSS: Modern dark dashboard with glassmorphism metric cards ----
# Selectors verified against Streamlit 1.35+.
st.markdown("""
<style>
    /* ── Global Canvas ── */
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .stApp { background: #0A0F1E; }

    /* ── Hide default Streamlit header chrome ── */
    #MainMenu, header, footer { visibility: hidden; }

    /* ── Sidebar ── */
    [data-testid="stSidebar"] {
        background: #0D1424;
        border-right: 1px solid rgba(245,166,35,0.15);
    }

    /* ── Tabs ── */
    [data-testid="stTabs"] [data-baseweb="tab-list"] {
        background: transparent;
        border-bottom: 1px solid rgba(255,255,255,0.08);
        gap: 4px;
    }
    [data-testid="stTabs"] [data-baseweb="tab"] {
        background: transparent;
        border-radius: 8px 8px 0 0;
        color: #8892A4;
        font-weight: 500;
        padding: 10px 20px;
    }
    [data-testid="stTabs"] [aria-selected="true"] {
        background: rgba(245,166,35,0.12) !important;
        color: #F5A623 !important;
        border-bottom: 2px solid #F5A623;
    }

    /* ── Glassmorphism KPI card ── */
    .kpi-card {
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 14px;
        padding: 20px 24px;
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        box-shadow: 0 4px 24px rgba(0,0,0,0.3);
        transition: border-color 0.2s;
    }
    .kpi-card:hover { border-color: rgba(245,166,35,0.3); }
    .kpi-card.insight { border-left: 3px solid #F6AD55; background: rgba(245,166,35,0.06); }
    .kpi-label  { font-size: 0.78rem; color: #8892A4; letter-spacing: 0.06em; text-transform: uppercase; margin-bottom: 6px; }
    .kpi-value  { font-size: 1.9rem; font-weight: 700; color: #E8EAF0; line-height: 1; }
    .kpi-delta  { font-size: 0.8rem; margin-top: 6px; }
    .kpi-delta.up   { color: #F5A623; }
    .kpi-delta.down { color: #22C55E; }
    .kpi-delta.bad  { color: #EF4444; }
    .kpi-subtitle   { font-size: 0.75rem; color: #A0AEC0; margin-top: 6px; }

    /* ── Styled Selectboxes / Dropdowns ── */
    select {
        background-color: #1e2433 !important;
        border: 1px solid #2d3748 !important;
        color: #e2e8f0 !important;
        border-radius: 6px !important;
        padding: 6px 32px 6px 10px !important;
        appearance: none !important;
        -webkit-appearance: none !important;
        background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='%236b7280' d='M6 8L1 3h10z'/%3E%3C/svg%3E") !important;
        background-repeat: no-repeat !important;
        background-position: right 10px center !important;
        width: 100% !important;
        cursor: pointer !important;
    }
    div[data-testid="stSelectbox"] > div {
        background-color: #1e2433 !important;
        border: 1px solid #2d3748 !important;
        color: #e2e8f0 !important;
        border-radius: 8px !important;
    }
    div[data-baseweb="select"] {
        background-color: #1e2433 !important;
    }
    ul[role="listbox"] {
        background-color: #1e2433 !important;
        border: 1px solid #2d3748 !important;
        border-radius: 8px !important;
    }
    li[role="option"] {
        color: #e2e8f0 !important;
    }
    li[role="option"]:hover, li[role="option"][aria-selected="true"] {
        background-color: rgba(245, 166, 35, 0.15) !important;
        color: #F5A623 !important;
    }

    /* ── Slider thumb affordance ── */
    div[data-testid="stSlider"] [role="slider"] {
        cursor: grab !important;
        border: 2px solid #F5A623 !important;
        background: #0A0F1E !important;
    }
    div[data-testid="stSlider"] [role="slider"]:active {
        cursor: grabbing !important;
    }
    div[data-testid="stSlider"] [data-testid="stTickBarMin"],
    div[data-testid="stSlider"] [data-testid="stTickBarMax"] {
        color: #A0AEC0 !important;
    }

    /* ── Alert banner ── */
    .info-banner {
        background: rgba(245,166,35,0.08);
        border-left: 3px solid #F5A623;
        border-radius: 0 8px 8px 0;
        padding: 10px 16px;
        font-size: 0.85rem;
        color: #C4A35A;
        margin-bottom: 16px;
    }

    /* ── Plotly chart container ── */
    [data-testid="stPlotlyChart"] {
        border-radius: 12px;
        overflow: hidden;
        border: 1px solid rgba(255,255,255,0.06);
    }
</style>
""", unsafe_allow_html=True)

# Shared Plotly dark layout defaults
PLOT_LAYOUT = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter", color="#8892A4"),
    margin=dict(l=10, r=10, t=40, b=90), # increased bottom margin for horizontal legend with breathing room
    hovermode="x unified",
    hoverlabel=dict(bgcolor="#121929", bordercolor="#2A3347", font_size=13),
    legend=dict(
        orientation="h",
        yanchor="top",
        y=-0.18, # positioned lower below chart
        xanchor="left",
        x=0,
        font=dict(size=12, color="#cbd5e1"), # larger, higher contrast text
        itemwidth=40, # wider color swatch
        tracegroupgap=0,
        bgcolor="rgba(0,0,0,0)",
        bordercolor="rgba(0,0,0,0)"
    ),
    modebar=dict(remove='all'), # hide Plotly default toolbar globally
    xaxis=dict(gridcolor="rgba(255,255,255,0.05)", showline=False),
    yaxis=dict(gridcolor="rgba(255,255,255,0.05)", showline=False),
)

# Global configuration to hide the Plotly modebar in Streamlit
PLOT_CONFIG = {'displayModeBar': False}

ACCENT      = "#F5A623"   # amber / energy
ACCENT_ALT  = "#22C55E"   # green / reference
DANGER      = "#EF4444"   # red / warning
BLUE        = "#3B82F6"   # blue / reference
SPREAD      = "#A855F7"   # violet / net product spread (distinct from amber pump price)

# Fuel Discount periods
DISCOUNT_PERIODS = [
    ("2022-06-01", "2022-08-31", "1st Fuel Discount (Tankrabatt 1) / 1. Tankrabatt"),
    ("2026-05-01", "2026-06-30", "2nd Fuel Discount (Tankrabatt 2) / 2. Tankrabatt"),
]
STABLE_MARGIN_BASELINE_DAYS = 365

# Canonical English event keys used internally (filtering, data columns).
EVENT_NAME_KEYS = {
    "Tankrabatt 1 Start (Jun 2022)": "policy_event_1_start",
    "Tankrabatt 1 End (Sep 2022)":   "policy_event_1_end",
    "Tankrabatt 2 Start (May 2026)": "policy_event_2_start",
}

# Official legislative milestones per event, sourced from docs/policy_timeline_tankrabatt.md
# Each tuple: (phase_label_translation_key, date, color)
# Relative day = calendar_date - effective_date, always negative (pre-event)
POLICY_MILESTONES = {
    "Tankrabatt 1 Start (Jun 2022)": [
        # (phase_label_key, date, hex_color)
        ("phase_public_rumour",      date(2022, 3, 14), "#6B7280"),   # Day −79 — grey
        ("phase_official_announcement", date(2022, 3, 24), "#F5A623"),   # Day −69 — amber
        ("phase_draft_law",          date(2022, 5, 10), "#60A5FA"),   # Day −22 — light blue
        ("phase_parliamentary_vote", date(2022, 5, 19), "#3B82F6"),   # Day −13 — blue / legal certainty
    ],
    "Tankrabatt 1 End (Sep 2022)": [
        # End was legally certain from Day 1 of the discount (fixed 3-month term in the law)
        # The only "anticipation" milestone is the start of the discount itself (Day −92)
        ("phase_expiry_fixed",       date(2022, 6, 1),  "#F5A623"),   # Day −92 — amber / known from start
    ],
    "Tankrabatt 2 Start (May 2026)": [
        ("phase_announcement_draft", date(2026, 4, 15), "#F5A623"),   # Day −16 — amber
        ("phase_parliamentary_vote", date(2026, 4, 24), "#10B981"),   # Day −7  — green / legal certainty
    ],
}

@st.cache_data
def load_translations():
    translations_dir = Path(__file__).parent / "translations"
    translations = {}
    for lang in ["en", "de"]:
        json_path = translations_dir / f"{lang}.json"
        if json_path.exists():
            with open(json_path, "r", encoding="utf-8") as f:
                translations[lang] = json.load(f)
        else:
            translations[lang] = {}
    return translations

TRANSLATIONS = load_translations()

# Default translate helper used before the sidebar re-binds it to the selected language.
def translate(key: str) -> str:
    return TRANSLATIONS.get("en", {}).get(key, key)

def detect_default_language() -> str:
    candidates = []
    try:
        candidates.append(st.context.locale)
    except Exception:
        pass
    candidates.append(os.environ.get("LANG", ""))
    return "de" if any(str(value).lower().startswith("de") for value in candidates if value) else "en"

# ==========================================
# 2. DATA PIPELINE (Vectorized — no loops)
# ==========================================

def _compute_smoothing(df: pl.DataFrame, smoothing_days: int, partition_cols: list[str] = None) -> pl.DataFrame:
    """
    Applies a rolling mean to raw/product columns and recalculates margins.
    If partition_cols is provided, the rolling mean is computed over each group.
    """
    if smoothing_days <= 1:
        return df

    cols_to_smooth = [
        "Raw_Material_EUR_per_Liter",
        "brent_eur_liter",
        "e5_product_eur_liter",
        "e10_product_eur_liter",
        "diesel_product_eur_liter",
    ]

    # Dynamically apply rolling mean with or without grouping
    expressions = []
    for col in cols_to_smooth:
        expr = pl.col(col).rolling_mean(window_size=smoothing_days, min_periods=1)
        if partition_cols:
            expr = expr.over(partition_cols)
        expressions.append(expr.alias(col))

    df = df.sort("date").with_columns(expressions)

    # Recalculate margins based on smoothed values
    df = df.with_columns([
        (pl.col("e5_net_price") - pl.col("Raw_Material_EUR_per_Liter")).alias("margin_e5"),
        (pl.col("e10_net_price") - pl.col("Raw_Material_EUR_per_Liter")).alias("margin_e10"),
        (pl.col("diesel_net_price") - pl.col("Raw_Material_EUR_per_Liter")).alias("margin_diesel"),
        (pl.col("e5_net_price") - pl.col("e5_product_eur_liter")).alias("retail_margin_e5"),
        (pl.col("e10_net_price") - pl.col("e10_product_eur_liter")).alias("retail_margin_e10"),
        (pl.col("diesel_net_price") - pl.col("diesel_product_eur_liter")).alias("retail_margin_diesel"),
        (pl.col("e5_product_eur_liter") - pl.col("Raw_Material_EUR_per_Liter")).alias("refining_spread_e5"),
        (pl.col("e10_product_eur_liter") - pl.col("Raw_Material_EUR_per_Liter")).alias("refining_spread_e10"),
        (pl.col("diesel_product_eur_liter") - pl.col("Raw_Material_EUR_per_Liter")).alias("refining_spread_diesel"),
    ])
    return df

@st.cache_data(show_spinner="Loading aggregated spreads + taxes… / Lade aggregierte Spannen + Steuern…")
def load_data(start_date: date = date(2021, 1, 1), smoothing_days: int = 1):
    """
    Loads the real aggregated daily spreads (Tankerkönig + Macro).
    """
    df = pl.read_parquet(DATA_DIR / "processed_daily_margins.parquet")
    df = df.filter(pl.col("date") >= start_date)
    df = _compute_smoothing(df, smoothing_days)
    return df

@st.cache_data(show_spinner="Loading intraday rhythm… / Lade Tagesrhythmus…")
def load_intraday_data():
    if not INTRADAY_FILE.exists():
        return None
    return pl.read_parquet(INTRADAY_FILE)

@st.cache_data(show_spinner="Loading brand comparison data… / Lade Markenvergleichsdaten…")
def load_brand_daily_data(smoothing_days: int = 1):
    if not BRAND_DAILY_FILE.exists():
        return None
    df = pl.read_parquet(BRAND_DAILY_FILE)
    df = _compute_smoothing(df, smoothing_days, partition_cols=["analysis_level", "comparison_group"])
    return df

@st.cache_data(show_spinner="Loading regional pricing data… / Lade regionale Preisdaten…")
def load_regional_daily_data(smoothing_days: int = 1):
    if not REGIONAL_DAILY_FILE.exists():
        return None
    df = pl.read_parquet(REGIONAL_DAILY_FILE)
    df = _compute_smoothing(df, smoothing_days, partition_cols=["region"])
    return df

# ==========================================
# 3. SIDEBAR — Controls
# ==========================================

default_language = detect_default_language()
language_labels = {"en": "English", "de": "Deutsch"}
language_index = list(language_labels).index(default_language)

with st.sidebar:
    selected_language = st.selectbox(
        translate("language"),
        options=list(language_labels),
        index=language_index,
        format_func=lambda key: language_labels[key],
    )
    lang = selected_language
    translations = TRANSLATIONS[lang]

    def translate(key: str) -> str:
        return translations[key]

    st.markdown(f"## {translate('app_short')}")
    st.markdown(f"<div style='color:#8892A4;font-size:0.8rem;margin-bottom:16px;'>{translate('app_subtitle')}</div>", unsafe_allow_html=True)

    # Pre-load data with 1-day smoothing to extract min/max dates for header and range slider
    full_data_df = load_data(smoothing_days=1)
    raw_min = full_data_df["date"].min()
    raw_max = full_data_df["date"].max()
    min_d = raw_min.to_python() if hasattr(raw_min, 'to_python') else raw_min
    max_d = raw_max.to_python() if hasattr(raw_max, 'to_python') else raw_max

    st.markdown(
        f"<div style='background-color:#121929; border: 1px solid #1E293B; border-radius: 4px; padding: 10px; margin-bottom:15px; font-size:0.8rem; color:#E8EAF0;'>"
        f"<strong>{translate("app_version_label")}</strong> v1.1.0<br>"
        f"<strong>{translate("data_through_label")}</strong> {max_d.strftime('%Y-%m-%d')}"
        f"</div>",
        unsafe_allow_html=True
    )
    st.divider()

    smoothing_options = {
        1: translate("smooth_daily"),
        7: translate("smooth_weekly"),
        14: translate("smooth_biweekly"),
        30: translate("smooth_monthly"),
    }
    smoothing_days = st.selectbox(
        translate("procurement_smoothing"),
        list(smoothing_options),
        index=0,
        format_func=lambda key: smoothing_options[key],
        help=translate("procurement_smoothing_help")
    )

    df_full = load_data(smoothing_days=smoothing_days)

    date_range = st.slider(
        translate("date_range"),
        min_value=min_d, max_value=max_d,
        value=(date(2022, 1, 1), max_d),
        help=translate("date_range_help") + " " + translate("date_range_drag_help")
    )

    fuel_options = {"e5": translate("fuel_e5"), "e10": translate("fuel_e10"), "diesel": translate("fuel_diesel")}
    fuel_key = st.selectbox(
        translate("fuel_type"),
        list(fuel_options),
        index=0
        , format_func=lambda key: fuel_options[key]
    )
    fuel_type = fuel_options[fuel_key]

    tax_viz_options = {
        "hide": translate("hide_taxes"),
        "combined": translate("taxes_combined"),
        "detailed": translate("taxes_detailed"),
    }
    tax_viz = st.selectbox(
        translate("tax_viz"),
        list(tax_viz_options),
        index=2,
        format_func=lambda key: tax_viz_options[key],
        help=translate("tax_viz_help")
    )

    st.divider()
    baseline_options = {
        "brent": translate("brent_baseline"),
        "refined": translate("refined_baseline"),
    }
    spread_baseline_mode = st.selectbox(
        translate("spread_baseline_mode"),
        list(baseline_options),
        index=0,
        format_func=lambda key: baseline_options[key]
    )

    st.divider()
    show_tax_trend = st.checkbox(translate("tax_trend"), value=False, help=translate("tax_trend_help"))
    
    st.divider()
    st.markdown(f"<div style='color:#4A5568;font-size:0.72rem;margin-top:auto;padding-top:24px;'>{translate('data_sources')}</div>", unsafe_allow_html=True)

# ==========================================
# 4. MAIN AREA
# ==========================================

st.markdown(f"## {translate('main_title')}")
st.markdown(f"<div style='color:#8892A4;margin-bottom:24px;'>{translate('main_subtitle')}</div>", unsafe_allow_html=True)

# Filter based on sidebar date range
df = df_full.filter(
    (pl.col("date") >= date_range[0]) & (pl.col("date") <= date_range[1])
).to_pandas()

# Map fuel type selection to column names
col_map = {
    "e5": {
        "price": "price_e5", "margin": "margin_e5", "net": "e5_net_price",
        "vat": "e5_vat", "ebv": "e5_ebv", "co2": "e5_co2", "energy": "e5_energy"
    },
    "e10": {
        "price": "price_e10", "margin": "margin_e10", "net": "e10_net_price",
        "vat": "e10_vat", "ebv": "e10_ebv", "co2": "e10_co2", "energy": "e10_energy"
    },
    "diesel": {
        "price": "price_diesel", "margin": "margin_diesel", "net": "diesel_net_price",
        "vat": "diesel_vat", "ebv": "diesel_ebv", "co2": "diesel_co2", "energy": "diesel_energy"
    }
}
pump_price_col = col_map[fuel_key]["price"]

# Dynamically override the margin column based on selection
if spread_baseline_mode == "refined" and f"retail_margin_{fuel_key}" in df.columns:
    margin_col = f"retail_margin_{fuel_key}"
else:
    margin_col = col_map[fuel_key]["margin"]

vat_col = col_map[fuel_key]["vat"]
ebv_col = col_map[fuel_key]["ebv"]
co2_col = col_map[fuel_key]["co2"]
energy_col = col_map[fuel_key]["energy"]

def mean_for_date_window(source_df: pl.DataFrame, value_col: str, start: date, end: date) -> float:
    window_df = source_df.filter((pl.col("date") >= start) & (pl.col("date") <= end))
    value = window_df[value_col].mean() if not window_df.is_empty() else None
    return float(value) if value is not None else float("nan")


def stable_pre_event_margin_baseline(
    source_df: pl.DataFrame,
    margin_col: str,
    event_start: date,
) -> tuple[date, date, float]:
    baseline_start = event_start - timedelta(days=STABLE_MARGIN_BASELINE_DAYS)
    baseline_end = event_start - timedelta(days=1)
    baseline_mean = mean_for_date_window(source_df, margin_col, baseline_start, baseline_end)
    return baseline_start, baseline_end, baseline_mean


# Calculate total tax for the "Combined" view
df["total_tax"] = df[vat_col] + df[ebv_col] + df[co2_col] + df[energy_col]

# Calculate correlation (lagged by 2 days)
if len(df) > 10:
    corr_df = df_full.select(["date", "Raw_Material_EUR_per_Liter", pump_price_col]).drop_nulls().to_pandas()
    # Shift Brent by 2 days forward to align past Brent with today's Pump
    corr_val = corr_df["Raw_Material_EUR_per_Liter"].shift(2).corr(corr_df[pump_price_col])
else:
    corr_val = 0.0

# ── KPI Row ──────────────────────────────────────────────────────────────────
kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)

current_raw  = df["Raw_Material_EUR_per_Liter"].iloc[-1]
current_pump = df[pump_price_col].iloc[-1]
current_marg = df[margin_col].iloc[-1]

pre_disc_start, pre_disc_end, pre_disc = stable_pre_event_margin_baseline(
    df_full, margin_col, date(2022, 6, 1)
)
disc_marg = mean_for_date_window(df_full, margin_col, date(2022, 6, 1), date(2022, 8, 31))
delta_marg = disc_marg - pre_disc if not (pre_disc != pre_disc or disc_marg != disc_marg) else 0

with kpi1:
    st.markdown(f"""<div class='kpi-card'>
        <div class='kpi-label'>{translate('brent')}</div>
        <div class='kpi-value'>€{current_raw:.3f}</div>
        <div class='kpi-subtitle'>{translate('raw_material_cost')}</div>
    </div>""", unsafe_allow_html=True)

with kpi2:
    st.markdown(f"""<div class='kpi-card'>
        <div class='kpi-label'>{translate('pump_price')} ({fuel_type})</div>
        <div class='kpi-value'>€{current_pump:.3f}</div>
        <div class='kpi-subtitle'>{translate('national_avg')}</div>
    </div>""", unsafe_allow_html=True)

with kpi3:
    st.markdown(f"""<div class='kpi-card'>
        <div class='kpi-label'>{translate('net_spread')}</div>
        <div class='kpi-value'>€{current_marg:.3f}</div>
        <div class='kpi-subtitle'>{translate('spread_kpi_note')}</div>
    </div>""", unsafe_allow_html=True)

with kpi4:
    sign = "+" if delta_marg > 0 else ""
    st.markdown(f"""<div class='kpi-card insight'>
        <div class='kpi-label'>{translate('spread_delta_discount_1')}</div>
        <div class='kpi-value'>{sign}€{delta_marg:.3f}</div>
        <div class='kpi-subtitle'>{translate('pre_discount_compared')}</div>
    </div>""", unsafe_allow_html=True)

with kpi5:
    corr_label = translate("kpi_brent_correlation")
    corr_sub = translate("kpi_brent_correlation_subtitle")
    corr_str = f"{corr_val*100:.1f}%" if corr_val != 0.0 else translate("not_available")
    st.markdown(f"""<div class='kpi-card'>
        <div class='kpi-label'>{corr_label}</div>
        <div class='kpi-value'>{corr_str}</div>
        <div class='kpi-subtitle'>{corr_sub}</div>
    </div>""", unsafe_allow_html=True)

    # Tiny sparkline: rolling 30-day Brent-pump correlation
    if corr_val != 0.0 and len(corr_df) > 30:
        rolling_corr = (
            corr_df["Raw_Material_EUR_per_Liter"]
            .shift(2)
            .rolling(window=30, min_periods=5)
            .corr(corr_df[pump_price_col])
        )
        fig_spark = go.Figure(go.Scatter(
            x=corr_df["date"],
            y=rolling_corr,
            mode="lines",
            line=dict(color=ACCENT, width=1.5),
            fill="tozeroy",
            fillcolor="rgba(245,166,35,0.08)",
            hovertemplate="30d correlation: %{y:.2f}<extra></extra>",
        ))
        fig_spark.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=0, r=0, t=0, b=0),
            xaxis=dict(visible=False),
            yaxis=dict(visible=False, range=[0, 1]),
            height=55,
            showlegend=False,
        )
        st.plotly_chart(fig_spark, use_container_width=True, config=PLOT_CONFIG)

st.markdown("<br>", unsafe_allow_html=True)

# ── Tabs ────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab_brand, tab4 = st.tabs([
    translate("tab_brent"),
    translate("tab_spread"),
    translate("tab_rhythm"),
    translate("tab_brand"),
    translate("tab_location"),
])

# ── Helper: Add Discount Highlight Bands ─────────────────────────────────────
def add_discount_bands(fig):
    colors = ["rgba(245,166,35,0.12)", "rgba(59,130,246,0.10)"]
    visible_min = df["date"].astype(str).min()
    visible_max = df["date"].astype(str).max()
    for (x0, x1, label), color in zip(DISCOUNT_PERIODS, colors):
        if x0 <= visible_max and x1 >= visible_min:
            fig.add_vrect(
                x0=x0, x1=x1, fillcolor=color, opacity=1,
                layer="below", line_width=1, line_color="rgba(245,166,35,0.3)"
            )
            # Clamp the horizontal start position to visible area
            anno_x = max(x0, visible_min)
            
            # Determine alignment anchor dynamically to prevent overflowing the right edge
            try:
                from datetime import datetime
                d_anno = datetime.strptime(anno_x, "%Y-%m-%d")
                d_max = datetime.strptime(visible_max, "%Y-%m-%d")
                if (d_max - d_anno).days < 45:
                    anchor = "right"
                else:
                    anchor = "left"
            except Exception:
                anchor = "left"

            fig.add_annotation(
                x=anno_x,
                y=0.98,
                xref="x",
                yref="paper",
                text=label,
                showarrow=False,
                xanchor=anchor,
                yanchor="top",
                font=dict(color="#F5A623", size=11),
                bgcolor="rgba(10,15,30,0.85)",
                bordercolor="rgba(245,166,35,0.45)",
                borderwidth=1,
                borderpad=4,
                opacity=0.95,
            )
    return fig


def calculate_tax_break_pass_through(source_df: pl.DataFrame) -> list[dict[str, object]]:
    """Compare pump-price drops with tax-burden drops for each tax-break window."""
    max_date = source_df["date"].max()
    periods = [
        (translate("tankrabatt_1"), date(2022, 6, 1), date(2022, 8, 31)),
        (translate("tankrabatt_2"), date(2026, 5, 1), date(2026, 6, 30)),
    ]
    analysis_df = source_df.with_columns(
        (pl.col(vat_col) + pl.col(ebv_col) + pl.col(co2_col) + pl.col(energy_col)).alias("selected_total_tax")
    )
    rows = []

    for label, start, planned_end in periods:
        if start > max_date:
            continue

        actual_end = min(planned_end, max_date)
        period_days = (actual_end - start).days + 1
        pre_start = start - timedelta(days=period_days)
        pre_end = start - timedelta(days=1)
        spread_pre_start, spread_pre_end, spread_baseline = stable_pre_event_margin_baseline(
            analysis_df, margin_col, start
        )

        pre_df = analysis_df.filter((pl.col("date") >= pre_start) & (pl.col("date") <= pre_end))
        discount_df = analysis_df.filter((pl.col("date") >= start) & (pl.col("date") <= actual_end))
        if pre_df.is_empty() or discount_df.is_empty():
            continue

        pump_drop = pre_df[pump_price_col].mean() - discount_df[pump_price_col].mean()
        tax_drop = pre_df["selected_total_tax"].mean() - discount_df["selected_total_tax"].mean()
        discount_spread = discount_df[margin_col].mean()
        spread_change = (
            discount_spread - spread_baseline
            if not (spread_baseline != spread_baseline or discount_spread is None)
            else float("nan")
        )
        raw_change = discount_df["Raw_Material_EUR_per_Liter"].mean() - pre_df["Raw_Material_EUR_per_Liter"].mean()
        pass_through = (pump_drop / tax_drop) if tax_drop else None

        rows.append({
            "event": label,
            "pump_drop": pump_drop,
            "tax_drop": tax_drop,
            "spread_change": spread_change,
            "raw_change": raw_change,
            "pass_through": pass_through,
            "window": f"{start:%Y-%m-%d} – {actual_end:%Y-%m-%d}",
            "baseline": f"{pre_start:%Y-%m-%d} – {pre_end:%Y-%m-%d}",
            "spread_baseline": f"{spread_pre_start:%Y-%m-%d} – {spread_pre_end:%Y-%m-%d}",
        })

    return rows


def calculate_brand_policy_rows(
    source_df: pl.DataFrame,
    groups: list[str],
    event_start: date,
    planned_end: date,
) -> list[dict[str, object]]:
    max_date = source_df["date"].max()
    if max_date is None or event_start > max_date:
        return []

    actual_end = min(planned_end, max_date)
    rows = []
    for group in groups:
        group_df = source_df.filter(pl.col("comparison_group") == group)
        if group_df.is_empty():
            continue

        baseline_start, baseline_end, baseline_margin = stable_pre_event_margin_baseline(
            group_df, margin_col, event_start
        )
        discount_margin = mean_for_date_window(group_df, margin_col, event_start, actual_end)
        discount_price = mean_for_date_window(group_df, pump_price_col, event_start, actual_end)
        station_count = group_df["station_count"].max()
        if baseline_margin != baseline_margin or discount_margin != discount_margin:
            continue

        rows.append({
            "group": group,
            "station_count": int(station_count) if station_count is not None else 0,
            "baseline_margin": baseline_margin,
            "discount_margin": discount_margin,
            "delta_margin": discount_margin - baseline_margin,
            "discount_price": discount_price,
            "baseline_window": f"{baseline_start:%Y-%m-%d} – {baseline_end:%Y-%m-%d}",
            "discount_window": f"{event_start:%Y-%m-%d} – {actual_end:%Y-%m-%d}",
        })

    return sorted(rows, key=lambda row: row["delta_margin"], reverse=True)


def welch_normal_p_value(before: list[float], after: list[float]) -> tuple[float, float]:
    """Return difference in means and two-sided normal-approximated Welch p-value."""
    before = [value for value in before if value is not None]
    after = [value for value in after if value is not None]
    if len(before) < 2 or len(after) < 2:
        return float("nan"), float("nan")

    mean_before = sum(before) / len(before)
    mean_after = sum(after) / len(after)
    var_before = sum((value - mean_before) ** 2 for value in before) / (len(before) - 1)
    var_after = sum((value - mean_after) ** 2 for value in after) / (len(after) - 1)
    standard_error = sqrt(var_before / len(before) + var_after / len(after))
    if standard_error == 0:
        return mean_after - mean_before, 0.0

    z_score = (mean_after - mean_before) / standard_error
    p_value = erfc(abs(z_score) / sqrt(2.0))
    return mean_after - mean_before, p_value


def evidence_label(p_value: float) -> str:
    if p_value != p_value:
        return translate("not_available")
    if p_value < 0.01:
        return translate("strong")
    if p_value < 0.05:
        return translate("moderate")
    return translate("weak")


def calculate_switch_event_study(source_df: pl.DataFrame, window_days: int) -> list[dict[str, object]]:
    """Analyze observable tax-policy switches with symmetric before/after windows."""
    max_date = source_df["date"].max()
    min_date = source_df["date"].min()
    events = [
        ("tax_break_on_2022", date(2022, 6, 1)),
        ("tax_break_off_2022", date(2022, 9, 1)),
        ("tax_break_on_2026", date(2026, 5, 1)),
    ]
    analysis_df = source_df.with_columns([
        (pl.col(vat_col) + pl.col(ebv_col) + pl.col(co2_col) + pl.col(energy_col)).alias("selected_total_tax"),
        (pl.col(pump_price_col) - pl.col("Raw_Material_EUR_per_Liter")).alias("raw_adjusted_price"),
    ])
    rows = []

    for event_key, switch_date in events:
        if switch_date <= min_date or switch_date > max_date:
            continue

        before_start = max(min_date, switch_date - timedelta(days=window_days))
        before_end = switch_date - timedelta(days=1)
        after_start = switch_date
        after_end = min(max_date, switch_date + timedelta(days=window_days - 1))

        before_df = analysis_df.filter((pl.col("date") >= before_start) & (pl.col("date") <= before_end))
        after_df = analysis_df.filter((pl.col("date") >= after_start) & (pl.col("date") <= after_end))
        if before_df.height < 2 or after_df.height < 2:
            continue

        pump_change, pump_p = welch_normal_p_value(before_df[pump_price_col].to_list(), after_df[pump_price_col].to_list())
        raw_adjusted_change, raw_adjusted_p = welch_normal_p_value(
            before_df["raw_adjusted_price"].to_list(),
            after_df["raw_adjusted_price"].to_list(),
        )
        tax_change = after_df["selected_total_tax"].mean() - before_df["selected_total_tax"].mean()
        tax_pass_through = pump_change / tax_change if tax_change else None

        rows.append({
            "event_key": event_key,
            "before": f"{before_start:%Y-%m-%d} – {before_end:%Y-%m-%d}",
            "after": f"{after_start:%Y-%m-%d} – {after_end:%Y-%m-%d}",
            "n_before": before_df.height,
            "n_after": after_df.height,
            "pump_change": pump_change,
            "tax_change": tax_change,
            "tax_pass_through": tax_pass_through,
            "raw_adjusted_change": raw_adjusted_change,
            "pump_p": pump_p,
            "raw_adjusted_p": raw_adjusted_p,
        })

    return rows

def get_event_study_timeline(
    source_df: pl.DataFrame,
    pump_price_col: str,
    margin_col: str,
    window_days: int = 60,
    normalize: bool = True
) -> pl.DataFrame:
    """
    Extracts daily trajectories aligned around major policy switch dates (t=0 = effective date).

    The normalization baseline is computed from the full pre-effective window (Day -window to Day -1).
    We do NOT use a pinned announcement date because in democratic systems information diffuses
    gradually over weeks — a single announcement date gives false precision.

    Instead we shade the entire pre-effective window as a 'gradual information zone' and let the
    actual spread trajectory show whether and when the market started reacting.

    Each event carries an 'event_type' ('tax_cut' or 'tax_hike') because the direction of the
    pre-event incentive is fundamentally asymmetric:
      - tax_cut  → stations MIGHT discount early (competitive market share grab)
      - tax_hike → stations have EVERY incentive to raise prices BEFORE t=0,
                   so the official restoration appears smaller than it is
    """
    # (label, effective_date, event_type)
    # event_type drives the incentive annotation shown in the chart legend card
    events = [
        ("Tankrabatt 1 Start (Jun 2022)", date(2022, 6, 1),  "tax_cut"),
        ("Tankrabatt 1 End (Sep 2022)",   date(2022, 9, 1),  "tax_hike"),
        ("Tankrabatt 2 Start (May 2026)", date(2026, 5, 1),  "tax_cut"),
    ]

    records = []
    max_date = source_df["date"].max()

    for label, effective_date, event_type in events:
        if effective_date - timedelta(days=5) > max_date:
            continue

        start_d = effective_date - timedelta(days=window_days)
        end_d   = effective_date + timedelta(days=window_days)

        sub_df = source_df.filter((pl.col("date") >= start_d) & (pl.col("date") <= end_d)).sort("date")
        if sub_df.is_empty():
            continue

        # Baseline = entire pre-effective window (Day -window to Day -1).
        # We accept this contains any anticipation moves — the chart trajectory itself
        # will visually reveal if prices were already trending before t=0.
        pre_df = sub_df.filter(pl.col("date") < effective_date)
        baseline_mean_spread = pre_df[margin_col].mean() if not pre_df.is_empty() else 0.0
        baseline_mean_pump   = pre_df[pump_price_col].mean() if not pre_df.is_empty() else 0.0

        for row in sub_df.iter_rows(named=True):
            rel_day    = (row["date"] - effective_date).days
            spread_val = row[margin_col]
            pump_val   = row[pump_price_col]

            if normalize:
                spread_val -= baseline_mean_spread
                pump_val   -= baseline_mean_pump

            records.append({
                "Event":              label,
                "Event Type":         event_type,
                "Relative Day":       rel_day,
                "Net Product Spread": spread_val,
                "Pump Price":         pump_val,
                "Raw Material Price": row["Raw_Material_EUR_per_Liter"],
            })

    if not records:
        return pl.DataFrame(schema={
            "Event": pl.String, "Event Type": pl.String, "Relative Day": pl.Int64,
            "Net Product Spread": pl.Float64, "Pump Price": pl.Float64,
            "Raw Material Price": pl.Float64,
        })

    return pl.DataFrame(records)

# ──────────────────────────────────────────────────────────────────────────────
# TAB 1: Brent vs Pump
# ──────────────────────────────────────────────────────────────────────────────
with tab1:
    with st.container():
        st.markdown(f"<h4 style='margin:0;'>{translate('brent_vs_pump_title')} — {fuel_type}</h4>", unsafe_allow_html=True)
        st.markdown(f"<span style='color:#8892A4;font-size:0.85rem;'>{translate('brent_vs_pump_note')}</span>", unsafe_allow_html=True)

        fig = go.Figure()
        
        # Base Layer: Brent Crude
        fig.add_trace(go.Scatter(
            x=df["date"], y=df["Raw_Material_EUR_per_Liter"],
            name=translate("brent"),
            mode="lines",
            fill="tozeroy" if tax_viz == "hide" else None,
            fillcolor="rgba(34,197,94,0.08)" if tax_viz == "hide" else None,
            line=dict(color=ACCENT_ALT, width=2),
            stackgroup="one" if tax_viz != "hide" else None
        ))
        
        if tax_viz != "hide":
            if spread_baseline_mode == "refined" and f"refining_spread_{fuel_key}" in df.columns:
                # 1. Refining Margin Layer
                ref_spread_col = f"refining_spread_{fuel_key}"
                refining_pct = (df[ref_spread_col] / df[pump_price_col]) * 100
                fig.add_trace(go.Scatter(
                    x=df["date"], y=df[ref_spread_col],
                    name=translate("refining_trace"),
                    mode="lines",
                    line=dict(width=0),
                    fillcolor="rgba(148, 163, 184, 0.45)", # Slate-400
                    stackgroup="one",
                    hovertemplate=translate("refining_trace") + ": €%{y:.3f} (%{customdata:.1f}%)<extra></extra>",
                    customdata=refining_pct
                ))
                
                # 2. Net Retail Spread Layer
                retail_margin_col = f"retail_margin_{fuel_key}"
                retail_pct = (df[retail_margin_col] / df[pump_price_col]) * 100
                fig.add_trace(go.Scatter(
                    x=df["date"], y=df[retail_margin_col],
                    name=translate("retail_trace"),
                    mode="lines",
                    line=dict(width=0),
                    fillcolor="rgba(168, 85, 247, 0.45)", # Violet / Net Spread
                    stackgroup="one",
                    hovertemplate=translate("retail_trace") + ": €%{y:.3f} (%{customdata:.1f}%)<extra></extra>",
                    customdata=retail_pct
                ))
            else:
                # Add standard net product spread layer
                margin_pct = (df[margin_col] / df[pump_price_col]) * 100
                fig.add_trace(go.Scatter(
                    x=df["date"], y=df[margin_col],
                    name=translate("spread_trace"),
                    mode="lines",
                    line=dict(width=0),
                    fillcolor="rgba(168, 85, 247, 0.45)", # Violet / Net Spread
                    stackgroup="one",
                    hovertemplate=translate("spread_hover") + ": €%{y:.3f} (%{customdata:.1f}%)<extra></extra>",
                    customdata=margin_pct
                ))

        if tax_viz == "combined":
            tax_pct = (df["total_tax"] / df[pump_price_col]) * 100
            fig.add_trace(go.Scatter(
                x=df["date"], y=df["total_tax"],
                name=translate("total_taxes"),
                mode="lines",
                line=dict(width=0),
                fillcolor="rgba(100, 116, 139, 0.4)", # Slate-500
                stackgroup="one",
                hovertemplate=translate("total_taxes") + ": €%{y:.3f} (%{customdata:.1f}%)<extra></extra>",
                customdata=tax_pct
            ))
            
        elif tax_viz == "detailed":
            # Plot in order from bottom to top: EBV -> CO2 -> Energy -> VAT
            # using a cohesive slate/indigo gradient
            tax_layers = [
                (ebv_col, translate("ebv"), "#334155"),       # Slate-700
                (co2_col, translate("co2"), "#475569"),       # Slate-600
                (energy_col, translate("energy_tax"), "#94a3b8"),   # Slate-400
                (vat_col, translate("vat"), "#64748b")        # Slate-500
            ]
            
            for col, name, color in tax_layers:
                layer_pct = (df[col] / df[pump_price_col]) * 100
                fig.add_trace(go.Scatter(
                    x=df["date"], y=df[col],
                    name=name,
                    mode="lines",
                    line=dict(width=0),
                    fillcolor=color,
                    stackgroup="one",
                    hovertemplate=name + ": €%{y:.3f} (%{customdata:.1f}%)<extra></extra>",
                    customdata=layer_pct
                ))

        # Top Layer: Pump Price (Independent line, not stacked)
        fig.add_trace(go.Scatter(
            x=df["date"], y=df[pump_price_col],
            name=f"{translate('pump_price')} — {fuel_type}",
            mode="lines",
            line=dict(color=ACCENT, width=2.5),
        ))
        
        fig = add_discount_bands(fig)
        
        # Determine max Y axis to keep charts stable
        max_y = df[pump_price_col].max() * 1.1
        fig.update_layout(**PLOT_LAYOUT, height=480, yaxis_title=translate("axis_euro_per_liter"), yaxis_range=[0, max_y])
        st.plotly_chart(fig, use_container_width=True, config=PLOT_CONFIG)


            
        if show_tax_trend:
            st.markdown(f"#### {translate('tax_burden_title')}")
            st.markdown(f"<span style='color:#8892A4;font-size:0.85rem;'>{translate('tax_burden_note')}</span>", unsafe_allow_html=True)
            
            tax_pct_series = (df["total_tax"] / df[pump_price_col]) * 100
            rolling_avg = tax_pct_series.rolling(window=90, min_periods=1).mean()
            
            fig_trend = go.Figure()
            fig_trend.add_trace(go.Scatter(
                x=df["date"], y=tax_pct_series,
                name=translate("tax_trace_daily"),
                mode="lines",
                line=dict(color="rgba(148, 163, 184, 0.3)", width=1),
            ))
            fig_trend.add_trace(go.Scatter(
                x=df["date"], y=rolling_avg,
                name=translate("tax_trace_90d"),
                mode="lines",
                line=dict(color="#3B82F6", width=3), # Blue
            ))
            fig_trend = add_discount_bands(fig_trend)
            # Add horizontal line for 50%
            threshold_label = translate("tax_threshold_50")
            fig_trend.add_hline(y=50, line_dash="dot", line_color=BLUE, line_width=1,
                   annotation_text=threshold_label, annotation_font_color=BLUE)
            fig_trend.update_layout(**PLOT_LAYOUT, height=350, yaxis_title=translate("tax_percent"), yaxis_ticksuffix="%")
            st.plotly_chart(fig_trend, use_container_width=True, config=PLOT_CONFIG)

# ──────────────────────────────────────────────────────────────────────────────
# TAB 2: Net Product Spread
# ──────────────────────────────────────────────────────────────────────────────
with tab2:
    if spread_baseline_mode == "refined":
        st.markdown(f"#### {translate('retail_spread_title')}")
        st.markdown(f"<span style='color:#8892A4;font-size:0.85rem;'>{translate('retail_spread_note')}</span>", unsafe_allow_html=True)
    else:
        st.markdown(f"#### {translate('spread_title')}")
        st.markdown(f"<span style='color:#8892A4;font-size:0.85rem;'>{translate('spread_note')}</span>", unsafe_allow_html=True)

    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(
        x=df["date"], y=df[margin_col],
        name=translate("spread_trace"), fill="tozeroy",
        fillcolor="rgba(245,166,35,0.07)",
        line=dict(color=ACCENT, width=2.5),
    ))
    # Baseline reference line
    baseline = df[margin_col].mean()
    fig2.add_hline(y=baseline, line_dash="dot", line_color=BLUE, line_width=1,
                   annotation_text=f" {translate('historical_avg')}: €{baseline:.3f}", annotation_font_color=BLUE)
    fig2 = add_discount_bands(fig2)
    fig2.update_layout(
        **{**PLOT_LAYOUT, "margin": dict(l=70, r=10, t=40, b=90)},
        height=400,
        yaxis_title=f"{translate('net_spread')} (€/L)",
    )
    st.plotly_chart(fig2, use_container_width=True, config=PLOT_CONFIG)

    # Sub-metrics below chart
    st.markdown("<br>", unsafe_allow_html=True)
    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric(translate("pre_discount_avg"), f"€{pre_disc:.4f}")
            st.caption(f"{pre_disc_start:%Y-%m-%d} – {pre_disc_end:%Y-%m-%d}")
        with c2:
            sign = "+" if delta_marg > 0 else ""
            st.metric(translate("during_discount_1"), f"€{disc_marg:.4f}", f"{sign}€{delta_marg:.4f}", delta_color="inverse")
        with c3:
            st.metric(translate("historical_range"), f"€{df[margin_col].min():.3f} – €{df[margin_col].max():.3f}")

    st.markdown(f"#### {translate('pass_title')}")
    st.markdown(f"<span style='color:#8892A4;font-size:0.85rem;'>{translate('pass_note')}</span>", unsafe_allow_html=True)

    pass_rows = calculate_tax_break_pass_through(df_full)
    if pass_rows:
        fig_pass = go.Figure()
        fig_pass.add_trace(go.Bar(
            x=[row["event"] for row in pass_rows],
            y=[row["pump_drop"] for row in pass_rows],
            name=translate("pump_drop"),
            marker_color=BLUE,
            text=[f"€{row['pump_drop']:.3f}" for row in pass_rows],
            textposition="outside",
        ))
        fig_pass.add_trace(go.Bar(
            x=[row["event"] for row in pass_rows],
            y=[row["tax_drop"] for row in pass_rows],
            name=translate("tax_drop"),
            marker_color=ACCENT,
            text=[f"€{row['tax_drop']:.3f}" for row in pass_rows],
            textposition="outside",
        ))
        fig_pass.update_layout(
            **PLOT_LAYOUT,
            height=360,
            barmode="group",
            yaxis_title=translate("axis_euro_per_liter"),
        )
        st.plotly_chart(fig_pass, use_container_width=True, config=PLOT_CONFIG)

        table_rows = []
        for row in pass_rows:
            pass_pct = row["pass_through"] * 100 if row["pass_through"] is not None else None
            table_rows.append({
                translate("event"): row["event"],
                translate("comparison_window"): f"{row['baseline']} vs. {row['window']}",
                translate("spread_baseline"): row["spread_baseline"],
                translate("pump_drop"): f"€{row['pump_drop']:.3f}/L",
                translate("tax_drop"): f"€{row['tax_drop']:.3f}/L",
                translate("pass_through"): f"{pass_pct:.1f}%" if pass_pct is not None else translate("not_available"),
                translate("spread_change"): f"{row['spread_change']:+.3f}/L",
                translate("raw_change"): f"{row['raw_change']:+.3f}/L",
            })
        st.dataframe(table_rows, hide_index=True, width="stretch")

    st.markdown(f"#### {translate('event_study_title')}")
    st.markdown(f"<span style='color:#8892A4;font-size:0.85rem;'>{translate('event_study_note')}</span>", unsafe_allow_html=True)

    # Controls row
    c_evt, c_win, c_opts = st.columns([2, 2, 1])

    all_event_labels = list(POLICY_MILESTONES.keys())
    with c_evt:
        selected_event = st.selectbox(
            translate("select_event_label"),
            options=all_event_labels,
            index=0,
            format_func=lambda key: translate(EVENT_NAME_KEYS.get(key, key)),
        )
    with c_win:
        event_window_days = st.slider(
            translate("event_window"),
            min_value=15, max_value=60, value=45, step=1,
            help=translate("event_window_help"),
        )
    with c_opts:
        normalize_opt   = st.checkbox(translate("checkbox_normalized"), value=True,
                                       help=translate("help_normalized"))
        show_milestones = st.checkbox(translate("checkbox_milestones"), value=True,
                                       help=translate("help_milestones"))

    timeline_data = get_event_study_timeline(
        df_full, pump_price_col, margin_col, window_days=event_window_days, normalize=normalize_opt
    )

    if not timeline_data.is_empty():
        timeline_pd = timeline_data.to_pandas()

        # Filter to ONE selected event only — no spaghetti
        group = timeline_pd[timeline_pd["Event"] == selected_event].copy()
        event_type = group["Event Type"].iloc[0] if not group.empty else "tax_cut"

        event_colors = {
            "Tankrabatt 1 Start (Jun 2022)": "#3B82F6",
            "Tankrabatt 1 End (Sep 2022)":   "#EF4444",
            "Tankrabatt 2 Start (May 2026)": "#10B981",
        }
        color = event_colors.get(selected_event, "#FFFFFF")

        fig_event = go.Figure()

        # Soft background shade: pre-event = information window, post-event = reaction zone
        fig_event.add_vrect(x0=-event_window_days, x1=0,
                            fillcolor=color, opacity=0.05, layer="below", line_width=0)
        fig_event.add_vrect(x0=0, x1=event_window_days,
                            fillcolor="rgba(255,255,255,0.02)", opacity=1, layer="below", line_width=0)

        # Main trajectory line
        if not group.empty:
            hover_fmt = translate("event_hover_normalized" if normalize_opt else "event_hover_absolute")
            fig_event.add_trace(go.Scatter(
                x=group["Relative Day"], y=group["Net Product Spread"],
                name=selected_event, mode="lines",
                line=dict(color=color, width=3),
                hovertemplate=hover_fmt
            ))

        # t=0 line
        fig_event.add_vline(
            x=0, line_dash="dash", line_color="rgba(136,146,164,0.75)", line_width=2,
            annotation_text=translate("tax_change_effective_arrow"),
            annotation_position="top right",
            annotation_font=dict(color="#8892A4", size=10)
        )

        # Policy milestone vlines for selected event only
        if show_milestones and selected_event in POLICY_MILESTONES:
            effective_dates = {
                "Tankrabatt 1 Start (Jun 2022)": date(2022, 6, 1),
                "Tankrabatt 1 End (Sep 2022)":   date(2022, 9, 1),
                "Tankrabatt 2 Start (May 2026)": date(2026, 5, 1),
            }
            eff_date = effective_dates[selected_event]
            for phase_label, milestone_date, phase_color in POLICY_MILESTONES[selected_event]:
                rel_day = (milestone_date - eff_date).days
                if rel_day < -event_window_days:
                    continue
                fig_event.add_vline(
                    x=rel_day, line_dash="dot", line_color=phase_color, line_width=1.5,
                    annotation_text=translate(phase_label),
                    annotation_position="top left",
                    annotation_font=dict(color=phase_color, size=9),
                )

        # Baseline reference
        if normalize_opt:
            fig_event.add_hline(y=0.0, line_dash="dot", line_color="rgba(255,255,255,0.1)", line_width=1)
            yaxis_title = translate("yaxis_spread_delta")
        else:
            yaxis_title = translate("yaxis_net_spread")

        event_layout = PLOT_LAYOUT | {
            "height": 400,
            "xaxis_title": translate("xaxis_days_relative"),
            "yaxis_title": yaxis_title,
            "showlegend": False,
        }
        fig_event.update_layout(**event_layout)
        st.plotly_chart(fig_event, use_container_width=True, config=PLOT_CONFIG)

        # ── Auto-generated interpretation: compute the numbers, show the verdict ──
        if not group.empty and normalize_opt:
            pre_spread  = group[group["Relative Day"] < 0]["Net Product Spread"].mean()
            post_spread = group[group["Relative Day"] >= 0]["Net Product Spread"].mean()
            delta       = post_spread - pre_spread

            if event_type == "tax_cut":
                # For a discount: did spread rise (retailers kept it) or stay flat/fall (passed through)?
                if delta > 0.01:
                    verdict = translate("verdict_discount_rose").format(delta=abs(delta))
                elif delta < -0.005:
                    verdict = translate("verdict_discount_fell").format(delta=abs(delta))
                else:
                    verdict = translate("verdict_discount_unchanged").format(delta=delta)
            else:
                # For a tax hike: did the spread compress before t=0 (pre-raising)?
                last_pre_days = group[(group["Relative Day"] >= -7) & (group["Relative Day"] < 0)]["Net Product Spread"].mean()
                if last_pre_days > 0.01:
                    verdict = translate("verdict_hike_pre_raised").format(last_pre_days=last_pre_days)
                else:
                    direction = translate("verdict_direction_fell" if delta < 0 else "verdict_direction_rose")
                    verdict = translate("verdict_hike_no_pre_raise").format(direction=direction, delta=abs(delta))

            event_display = translate(EVENT_NAME_KEYS.get(selected_event, selected_event))
            st.markdown(
                f"<div style='background:rgba(30,41,59,0.4);border-radius:8px;padding:12px 16px;"
                f"border:1px solid rgba(255,255,255,0.06);margin-top:8px;font-size:0.88rem;color:#C4CAD8;'>"
                f"<strong>{event_display}:</strong> {verdict}</div>",
                unsafe_allow_html=True
            )


# ──────────────────────────────────────────────────────────────────────────────
# TAB 3: Daily Rhythm
# ──────────────────────────────────────────────────────────────────────────────
with tab3:
    st.markdown(f"#### {translate('rhythm_title')}")
    st.markdown(f"<span style='color:#8892A4;font-size:0.85rem;'>{translate('rhythm_note')}</span>", unsafe_allow_html=True)

    intraday_df = load_intraday_data()

    if intraday_df is None:
        st.warning(translate("intraday_missing"))
        st.stop()
    
    # Define timeframes using strict Polars filtering
    timeframes = {
        "all_time": lambda df: df,
        "last_7": lambda df: df.filter(pl.col("date") >= (df.select(pl.col("date").max()).item() - timedelta(days=7))),
        "last_30": lambda df: df.filter(pl.col("date") >= (df.select(pl.col("date").max()).item() - timedelta(days=30))),
        "discount_2022": lambda df: df.filter((pl.col("date") >= date(2022, 6, 1)) & (pl.col("date") <= date(2022, 8, 31))),
        "discount_2026": lambda df: df.filter((pl.col("date") >= date(2026, 5, 1)) & (pl.col("date") <= date(2026, 6, 30))),
        "baseline_2021": lambda df: df.filter(pl.col("date") < date(2022, 1, 1)),
    }
    
    selected_timeframes = st.multiselect(
        translate("compare_timeframes"),
        options=list(timeframes.keys()),
        default=["all_time"],
        format_func=lambda key: translate(key),
    )
    
    fig3 = go.Figure()
    colors = [BLUE, ACCENT, ACCENT_ALT, DANGER, "#A78BFA"]
    
    primary_stats = None
    
    for i, tf_name in enumerate(selected_timeframes):
        filtered_df = timeframes[tf_name](intraday_df)
        if filtered_df.height == 0:
            continue
            
        # Group by hour and calculate mean for the selected fuel type
        agg_col = col_map[fuel_key]["price"]
        
        hourly = filtered_df.group_by("hour").agg([
            pl.col(agg_col).mean().alias("avg_price")
        ]).sort("hour").to_pandas()
        
        color = colors[i % len(colors)]
        is_primary = (i == 0)
        
        fig3.add_trace(go.Scatter(
            x=hourly["hour"], y=hourly["avg_price"],
            name=translate(tf_name),
            mode="lines+markers" if is_primary else "lines",
            line=dict(color=color, width=3 if is_primary else 2),
            marker=dict(size=7, color=color) if is_primary else None,
        ))
        
        if primary_stats is None:
            min_overall = hourly["avg_price"].min()
            max_overall = hourly["avg_price"].max()
            best_h_overall = hourly.loc[hourly["avg_price"].idxmin(), "hour"]
            worst_h_overall = hourly.loc[hourly["avg_price"].idxmax(), "hour"]
            primary_stats = min_overall, max_overall, best_h_overall, worst_h_overall

    if primary_stats is not None:
        min_overall, max_overall, best_h_overall, worst_h_overall = primary_stats
        fig3.add_annotation(x=worst_h_overall, y=max_overall + 0.005, text=f"{translate('peak')} {worst_h_overall:02d}:00 (€{max_overall:.2f})", showarrow=True, arrowhead=2, arrowcolor=colors[0], font=dict(color=colors[0]))
        fig3.add_annotation(x=best_h_overall, y=min_overall - 0.01, text=f"{translate('lowest')} {best_h_overall:02d}:00 (€{min_overall:.2f})", showarrow=True, arrowhead=2, arrowcolor=colors[0], font=dict(color=colors[0]))

    fig3.update_layout(**PLOT_LAYOUT, height=400, xaxis_title=translate("hour_of_day"), yaxis_title=translate("avg_pump_price"))
    fig3.update_xaxes(tickmode="linear", dtick=2, gridcolor="rgba(255,255,255,0.05)")
    st.plotly_chart(fig3, use_container_width=True, config=PLOT_CONFIG)

    if primary_stats is not None:
        st.info(f"**{translate('lowest_info')}:** {best_h_overall:02d}:00 (≈€{(max_overall - min_overall):.2f}/L {translate('below_peak')} {worst_h_overall:02d}:00). {translate('per_tank')} ~**€{50*(max_overall-min_overall):.1f}**.")

        # Legislative context callout (KPAnG 12:00 PM regulation)
        st.markdown(
            f"<div style='background-color:#121929; border: 1px solid #1E293B; border-radius: 6px; padding: 16px; margin-top: 15px; font-size:0.85rem; color:#E8EAF0;'>"
            f"<strong>{translate('regulatory_context_title')}</strong><br>"
            f"{translate('regulatory_context_body')}<br><br>"
            f"<ul>"
            f"<li><strong>{translate('regulatory_context_before_label')}</strong> {translate('regulatory_context_before')}</li>"
            f"<li><strong>{translate('regulatory_context_after_label')}</strong> {translate('regulatory_context_after')}</li>"
            f"</ul>"
            f"</div>",
            unsafe_allow_html=True
        )

# ──────────────────────────────────────────────────────────────────────────────
# TAB 4: Brand Comparison
# ──────────────────────────────────────────────────────────────────────────────
with tab_brand:
    st.markdown(f"#### {translate('brand_title')}")
    st.markdown(f"<span style='color:#8892A4;font-size:0.85rem;'>{translate('brand_note')}</span>", unsafe_allow_html=True)

    brand_df_full = load_brand_daily_data(smoothing_days=smoothing_days)

    if brand_df_full is None:
        st.warning(translate("brand_data_missing"))
    else:
        level_options = {
            "brand": translate("brand_level_brand"),
            "owner": translate("brand_level_owner"),
        }
        policy_windows = {
            "discount_2022": (translate("tankrabatt_1"), date(2022, 6, 1), date(2022, 8, 31)),
            "discount_2026": (translate("tankrabatt_2"), date(2026, 5, 1), date(2026, 6, 30)),
        }

        c_level, c_window = st.columns([2, 1])
        with c_level:
            selected_level = st.selectbox(
                translate("brand_level"),
                options=list(level_options),
                format_func=lambda key: level_options[key],
            )
        with c_window:
            selected_policy = st.selectbox(
                translate("policy_window"),
                options=list(policy_windows),
                format_func=lambda key: policy_windows[key][0],
            )

        level_df = brand_df_full.filter(pl.col("analysis_level") == selected_level)
        group_stats = (
            level_df.group_by("comparison_group")
            .agg(pl.col("station_count").max().alias("station_count"))
            .sort("station_count", descending=True)
        )
        group_options = group_stats["comparison_group"].to_list()
        default_groups = group_options[:8]

        selected_groups = st.multiselect(
            translate("brand_groups"),
            options=group_options,
            default=default_groups,
            help=translate("brand_groups_help"),
        )

        if selected_groups:
            visible_brand_df = level_df.filter(
                (pl.col("date") >= date_range[0])
                & (pl.col("date") <= date_range[1])
                & (pl.col("comparison_group").is_in(selected_groups))
            )

            fig_brand = go.Figure()
            brand_colors = [BLUE, ACCENT, ACCENT_ALT, DANGER, "#A78BFA", "#14B8A6", "#F97316", "#E879F9"]
            if not visible_brand_df.is_empty():
                trend_pd = visible_brand_df.sort(["comparison_group", "date"]).to_pandas()
                # Compute daily national average across all selected groups to normalize
                daily_national_avg = trend_pd.groupby("date")[margin_col].mean().rename("national_avg")
                trend_pd = trend_pd.merge(daily_national_avg, on="date", how="left")
                trend_pd["margin_vs_avg"] = (trend_pd[margin_col] - trend_pd["national_avg"]) * 100  # convert to euro-cents

                for idx, group_name in enumerate(selected_groups):
                    group_pd = trend_pd[trend_pd["comparison_group"] == group_name]
                    if group_pd.empty:
                        continue
                    # Apply 14-day smoothing for visual clarity
                    smoothed = group_pd.sort_values("date")["margin_vs_avg"].rolling(14, min_periods=1).mean()
                    fig_brand.add_trace(go.Scatter(
                        x=group_pd.sort_values("date")["date"],
                        y=smoothed,
                        name=group_name,
                        mode="lines",
                        line=dict(color=brand_colors[idx % len(brand_colors)], width=2.2),
                    ))

            fig_brand.add_hline(y=0.0, line_dash="dot", line_color="rgba(255,255,255,0.15)", line_width=1,
                                annotation_text=translate("national_avg_short"),
                                annotation_font_color="#8892A4")
            fig_brand = add_discount_bands(fig_brand)
            fig_brand.update_layout(
                **PLOT_LAYOUT,
                height=420,
                title=translate("brand_margin_trend"),
                yaxis_title=translate("brand_yaxis_margin_vs_avg"),
            )
            st.plotly_chart(fig_brand, use_container_width=True, config=PLOT_CONFIG)

            _, event_start, planned_end = policy_windows[selected_policy]
            brand_rows = calculate_brand_policy_rows(
                level_df,
                selected_groups,
                event_start,
                planned_end,
            )

            st.markdown(f"#### {translate('brand_delta_title')}")
            st.markdown(f"<span style='color:#8892A4;font-size:0.85rem;'>{translate('brand_delta_note')}</span>", unsafe_allow_html=True)

            if brand_rows:
                fig_brand_delta = go.Figure(go.Bar(
                    x=[row["group"] for row in brand_rows],
                    y=[row["delta_margin"] for row in brand_rows],
                    marker_color=[DANGER if row["delta_margin"] > 0 else ACCENT_ALT for row in brand_rows],
                    text=[f"{row['delta_margin']:+.3f}" for row in brand_rows],
                    textposition="outside",
                ))
                fig_brand_delta.add_hline(y=0, line_dash="dot", line_color="rgba(255,255,255,0.25)", line_width=1)
                fig_brand_delta.update_layout(
                    **PLOT_LAYOUT,
                    height=380,
                    yaxis_title=f"{translate('delta_margin')} (€/L)",
                    showlegend=False,
                )
                st.plotly_chart(fig_brand_delta, use_container_width=True, config=PLOT_CONFIG)

                table_rows = []
                for row in brand_rows:
                    table_rows.append({
                        translate("group"): row["group"],
                        translate("stations"): f"{row['station_count']:,}",
                        translate("baseline_margin"): f"€{row['baseline_margin']:.4f}/L",
                        translate("discount_margin"): f"€{row['discount_margin']:.4f}/L",
                        translate("delta_margin"): f"{row['delta_margin']:+.4f}/L",
                        translate("discount_price"): f"€{row['discount_price']:.4f}/L",
                        translate("spread_baseline"): row["baseline_window"],
                        translate("comparison_window"): row["discount_window"],
                    })
                st.dataframe(table_rows, hide_index=True, width="stretch")
            else:
                st.info(translate("brand_data_missing"))
        else:
            st.info(translate("brand_groups_help"))

# TAB 5: Regional Pricing Analysis
# ──────────────────────────────────────────────────────────────────────────────
with tab4:
    st.markdown(f"#### {translate('location_title')}")
    st.markdown(f"<span style='color:#8892A4;font-size:0.85rem;'>{translate('location_note')}</span>", unsafe_allow_html=True)

    reg_df = load_regional_daily_data(smoothing_days=smoothing_days)
    if reg_df is not None:
        margin_col = f"retail_margin_{fuel_key}"
        # Fall back to total margin if retail margin not available
        if margin_col not in reg_df.columns:
            margin_col = f"margin_{fuel_key}"

        start_dt = date_range[0]
        end_dt = date_range[1]

        # Filter to selected date range and drop the meaningless "Unknown Region" bucket (5 test stations)
        reg_window = reg_df.filter(
            (pl.col("date") >= start_dt)
            & (pl.col("date") <= end_dt)
            & (pl.col("region") != "Unknown Region")
        )

        if not reg_window.is_empty():
            # Compute national daily average margin, then each region's deviation
            daily_nat_avg = (
                reg_window.group_by("date")
                .agg(pl.col(margin_col).mean().alias("national_avg_margin"))
            )
            reg_enriched = reg_window.join(daily_nat_avg, on="date", how="left").with_columns(
                ((pl.col(margin_col) - pl.col("national_avg_margin")) * 100).alias("margin_delta_ct")
            )

            # ── Bar chart: average margin deviation per region (ct/L) ──
            bar_data = (
                reg_enriched.group_by("region")
                .agg([
                    pl.col("margin_delta_ct").mean().alias("avg_delta_ct"),
                    pl.col("station_count").max().alias("stations"),
                ])
                .sort("avg_delta_ct", descending=True)
                .to_pandas()
            )

            bar_colors = [DANGER if v > 0 else ACCENT_ALT for v in bar_data["avg_delta_ct"]]
            fig_reg_bar = go.Figure(go.Bar(
                x=bar_data["region"],
                y=bar_data["avg_delta_ct"],
                marker_color=bar_colors,
                text=[f"{v:+.2f} ct" for v in bar_data["avg_delta_ct"]],
                textposition="outside",
                textfont=dict(color="#E8EAF0", size=11),
            ))
            fig_reg_bar.add_hline(
                y=0.0, line_dash="dot", line_color="rgba(255,255,255,0.2)", line_width=1,
                annotation_text=translate("national_avg_short"),
                annotation_font_color="#8892A4"
            )
            fig_reg_bar.update_layout(
                **PLOT_LAYOUT, height=420, showlegend=False,
                yaxis_title=translate("regional_yaxis_margin_vs_avg"),
            )
            st.plotly_chart(fig_reg_bar, use_container_width=True, config=PLOT_CONFIG)

            # ── KPI metrics ──
            c1, c2, c3 = st.columns(3)
            most_exp = bar_data.iloc[0]
            cheapest = bar_data.iloc[-1]
            total_spread = most_exp["avg_delta_ct"] - cheapest["avg_delta_ct"]

            with c1:
                st.metric(
                    translate("most_expensive"),
                    most_exp["region"],
                    f"+{most_exp['avg_delta_ct']:.2f} ct/L",
                    delta_color="inverse"
                )
            with c2:
                st.metric(
                    translate("cheapest"),
                    cheapest["region"],
                    f"{cheapest['avg_delta_ct']:.2f} ct/L",
                    delta_color="normal"
                )
            with c3:
                st.metric(
                    translate("max_regional_premium"),
                    f"{total_spread:.2f} ct/L",
                    f"{50 * total_spread / 100:.2f}{translate('per_tank_suffix')}",
                )

            # ── Time series: regional margin evolution (14-day smoothed) ──
            st.markdown(f"#### {translate('regional_spread_title')}")
            reg_colors = [BLUE, ACCENT, ACCENT_ALT, DANGER, "#A78BFA", "#14B8A6", "#F97316", "#E879F9", "#6B7280", "#FBBF24"]
            regions_sorted = bar_data["region"].tolist()

            # Let users pick which regions to show
            selected_regions = st.multiselect(
                translate("regions_label"),
                options=regions_sorted,
                default=regions_sorted[:5],
            )

            if selected_regions:
                ts_data = (
                    reg_enriched.filter(pl.col("region").is_in(selected_regions))
                    .sort(["region", "date"])
                    .to_pandas()
                )

                fig_reg_ts = go.Figure()
                for idx, region_name in enumerate(selected_regions):
                    rg = ts_data[ts_data["region"] == region_name].sort_values("date")
                    if rg.empty:
                        continue
                    smoothed = rg["margin_delta_ct"].rolling(14, min_periods=1).mean()
                    fig_reg_ts.add_trace(go.Scatter(
                        x=rg["date"],
                        y=smoothed,
                        name=region_name,
                        mode="lines",
                        line=dict(color=reg_colors[idx % len(reg_colors)], width=2),
                    ))

                fig_reg_ts.add_hline(y=0.0, line_dash="dot", line_color="rgba(255,255,255,0.15)", line_width=1)
                fig_reg_ts = add_discount_bands(fig_reg_ts)
                fig_reg_ts.update_layout(
                    **PLOT_LAYOUT, height=400,
                    yaxis_title=translate("regional_ts_yaxis"),
                )
                st.plotly_chart(fig_reg_ts, use_container_width=True, config=PLOT_CONFIG)
        else:
            st.info(translate("regional_data_missing"))
    else:
        st.info(translate("regional_data_missing"))

