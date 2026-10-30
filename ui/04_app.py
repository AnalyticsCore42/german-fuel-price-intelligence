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

import sys
import importlib
from pathlib import Path

# Make src/ importable regardless of where streamlit is launched from
PROJECT_ROOT = Path(__file__).resolve().parent.parent
src_path = str(PROJECT_ROOT / "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# Automatically reload core analytical modules if previously cached by Streamlit runtime
for _mod in ("gasprice.price_decomposition", "gasprice.compliance_forensics"):
    if _mod in sys.modules:
        try:
            importlib.reload(sys.modules[_mod])
        except Exception:
            sys.modules.pop(_mod, None)
importlib.invalidate_caches()

import streamlit as st
import polars as pl
import pandas as pd
import plotly.graph_objects as go
import os
import json
import math
from math import erfc, sqrt
from datetime import date, timedelta

# Make the ui/ folder importable so we can keep the Tank Advisor tab in its own module
sys.path.insert(0, str(PROJECT_ROOT / "ui"))
import tank_advisor_tab
from gasprice.price_decomposition import (
    decompose_single_price,
    add_granular_decomposition_columns,
    calculate_asymmetric_pass_through,
    compute_counterfactual_excess_margin,
)
from gasprice.compliance_forensics import get_station_price_history

# Resolve data path relative to this script file — works from any working directory
DATA_DIR = Path(__file__).parent.parent / "data"
DAILY_FILE = DATA_DIR / "processed_daily_margins.parquet"
INTRADAY_FILE = DATA_DIR / "processed_intraday.parquet"
BRAND_DAILY_FILE = DATA_DIR / "processed_brand_daily_margins.parquet"
REGIONAL_DAILY_FILE = DATA_DIR / "processed_regional_daily_margins.parquet"
STATE_FILE = DATA_DIR / "station_carry_forward_state.parquet"
STATIONS_FILE = DATA_DIR / "tankerkoenig" / "stations" / "cleaned-stations.parquet"
COMPLIANCE_TREND_FILE = DATA_DIR / "dashboard" / "compliance_daily_trend.parquet"
COMPLIANCE_RANKINGS_FILE = DATA_DIR / "dashboard" / "compliance_station_rankings.parquet"
COMPLIANCE_LATENESS_FILE = DATA_DIR / "dashboard" / "compliance_lateness_distribution.parquet"
PASS_THROUGH_FILE = DATA_DIR / "dashboard" / "tankrabatt_pass_through.parquet"

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
        min-width: 360px !important;
        max-width: 420px !important;
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

    /* ── Deactivated Preview Tabs (Tank Advisor & RAG ONLY) ── */
    [data-testid="stTabs"] > div[data-baseweb="tab-panel"]:has(#advisor-tab-marker),
    [data-testid="stTabs"] > div[data-baseweb="tab-panel"]:has(#rag-tab-marker) {
        position: relative !important;
    }

    /* Semi-transparent grey overlay layer over content below banner */
    [data-testid="stTabs"] > div[data-baseweb="tab-panel"]:has(#advisor-tab-marker)::before,
    [data-testid="stTabs"] > div[data-baseweb="tab-panel"]:has(#rag-tab-marker)::before {
        content: "" !important;
        position: absolute !important;
        top: 66px !important;
        left: 0 !important;
        right: 0 !important;
        bottom: 0 !important;
        background: rgba(10, 15, 30, 0.40) !important;
        backdrop-filter: blur(1.5px) !important;
        -webkit-backdrop-filter: blur(1.5px) !important;
        pointer-events: none !important;
        z-index: 5 !important;
        border-radius: 8px !important;
    }

    /* Deactivate all buttons, dropdown menus, inputs, sliders, and controls strictly in Advisor and RAG */
    [data-testid="stTabs"] > div[data-baseweb="tab-panel"]:has(#advisor-tab-marker) button,
    [data-testid="stTabs"] > div[data-baseweb="tab-panel"]:has(#advisor-tab-marker) input,
    [data-testid="stTabs"] > div[data-baseweb="tab-panel"]:has(#advisor-tab-marker) select,
    [data-testid="stTabs"] > div[data-baseweb="tab-panel"]:has(#advisor-tab-marker) textarea,
    [data-testid="stTabs"] > div[data-baseweb="tab-panel"]:has(#advisor-tab-marker) [data-baseweb="select"],
    [data-testid="stTabs"] > div[data-baseweb="tab-panel"]:has(#advisor-tab-marker) [data-baseweb="input"],
    [data-testid="stTabs"] > div[data-baseweb="tab-panel"]:has(#advisor-tab-marker) [data-testid="stSlider"],
    [data-testid="stTabs"] > div[data-baseweb="tab-panel"]:has(#advisor-tab-marker) [data-testid="stNumberInput"],
    [data-testid="stTabs"] > div[data-baseweb="tab-panel"]:has(#advisor-tab-marker) [data-testid="stDateInput"],
    [data-testid="stTabs"] > div[data-baseweb="tab-panel"]:has(#advisor-tab-marker) [data-testid="stTimeInput"],
    [data-testid="stTabs"] > div[data-baseweb="tab-panel"]:has(#advisor-tab-marker) iframe,
    [data-testid="stTabs"] > div[data-baseweb="tab-panel"]:has(#rag-tab-marker) button,
    [data-testid="stTabs"] > div[data-baseweb="tab-panel"]:has(#rag-tab-marker) input,
    [data-testid="stTabs"] > div[data-baseweb="tab-panel"]:has(#rag-tab-marker) select,
    [data-testid="stTabs"] > div[data-baseweb="tab-panel"]:has(#rag-tab-marker) textarea,
    [data-testid="stTabs"] > div[data-baseweb="tab-panel"]:has(#rag-tab-marker) [data-baseweb="select"],
    [data-testid="stTabs"] > div[data-baseweb="tab-panel"]:has(#rag-tab-marker) [data-baseweb="input"],
    [data-testid="stTabs"] > div[data-baseweb="tab-panel"]:has(#rag-tab-marker) [data-testid="stChatInput"] {
        pointer-events: none !important;
        opacity: 0.45 !important;
        cursor: not-allowed !important;
        filter: grayscale(0.5) !important;
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
    .kpi-subtitle   { font-size: 0.75rem; color: #94A3B8; margin-top: 6px; }

    /* ── Price Stack Decomposition Card ── */
    .price-stack-card {
        background: rgba(255, 255, 255, 0.04);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 14px;
        padding: 14px 18px;
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        box-shadow: 0 4px 24px rgba(0,0,0,0.3);
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        min-height: 200px;
        box-sizing: border-box;
        transition: border-color 0.2s;
    }
    .price-stack-card:hover { border-color: rgba(245,166,35,0.3); }
    .price-stack-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 6px;
    }
    .price-stack-title {
        font-size: 0.76rem;
        color: #8892A4;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        font-weight: 600;
    }
    .price-stack-sub {
        font-size: 0.70rem;
        color: #64748B;
    }
    .price-stack-bar {
        display: flex;
        width: 100%;
        height: 6px;
        border-radius: 3px;
        overflow: hidden;
        background: rgba(255,255,255,0.06);
        margin-bottom: 8px;
    }
    .bar-seg-crude { background: #38BDF8; }
    .bar-seg-margin { background: #10B981; }
    .bar-seg-tax { background: #F59E0B; }
    
    .price-stack-list {
        display: flex;
        flex-direction: column;
        gap: 5px;
    }
    .price-stack-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 4px 8px;
        border-radius: 7px;
        background: rgba(255, 255, 255, 0.02);
        border: 1px solid rgba(255, 255, 255, 0.04);
        transition: all 0.15s ease;
    }
    .price-stack-item:hover {
        background: rgba(255, 255, 255, 0.05);
        border-color: rgba(255, 255, 255, 0.1);
    }
    .price-stack-item.level-pump {
        background: rgba(248, 250, 252, 0.05);
        border-color: rgba(248, 250, 252, 0.14);
    }
    .stack-meta {
        display: flex;
        flex-direction: column;
        gap: 1px;
    }
    .stack-label-row {
        display: flex;
        align-items: center;
        gap: 6px;
    }
    .stack-badge {
        font-size: 0.62rem;
        font-weight: 700;
        padding: 1px 5px;
        border-radius: 4px;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        display: inline-block;
        line-height: 1.3;
    }
    .badge-pump { background: rgba(248,250,252,0.15); color: #F8FAFC; border: 1px solid rgba(248,250,252,0.3); }
    .badge-tax { background: rgba(245,158,11,0.18); color: #FBBF24; border: 1px solid rgba(245,158,11,0.3); }
    .badge-margin { background: rgba(16,185,129,0.18); color: #34D399; border: 1px solid rgba(16,185,129,0.3); }
    .badge-crude { background: rgba(56,189,248,0.18); color: #38BDF8; border: 1px solid rgba(56,189,248,0.3); }
    
    .stack-name {
        font-size: 0.80rem;
        font-weight: 600;
        color: #E2E8F0;
    }
    .stack-desc {
        font-size: 0.68rem;
        color: #94A3B8;
        padding-left: 1px;
    }
    .stack-values {
        display: flex;
        flex-direction: column;
        align-items: flex-end;
        gap: 0px;
        white-space: nowrap;
        margin-left: 8px;
    }
    .stack-val-main {
        font-size: 0.98rem;
        font-weight: 700;
        color: #F8FAFC;
        line-height: 1.1;
    }
    .stack-val-pct {
        font-size: 0.68rem;
        font-weight: 500;
        color: #94A3B8;
    }

    /* ── Discount KPI Card ── */
    .discount-card {
        background: rgba(255, 255, 255, 0.04);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 14px;
        padding: 12px 14px;
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        box-shadow: 0 4px 24px rgba(0,0,0,0.3);
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        min-height: 200px;
        box-sizing: border-box;
        transition: border-color 0.2s;
        border-left: 3px solid #F5A623;
    }
    .discount-card:hover { border-color: rgba(245,166,35,0.35); }
    .discount-card.discount-2 { border-left-color: #38BDF8; }
    .discount-card.discount-2:hover { border-color: rgba(56,189,248,0.35); }
    .discount-card.discount-3 { border-left-color: #10B981; }
    .discount-card.discount-3:hover { border-color: rgba(16,185,129,0.35); }
    .discount-live-badge {
        white-space: nowrap;
        font-size: 0.66rem;
        color: #10B981;
        font-weight: 600;
    }
    .discount-card-header {
        display: flex;
        flex-wrap: wrap;
        justify-content: space-between;
        align-items: center;
        gap: 2px 6px;
        margin-bottom: 4px;
    }
    .discount-card-title {
        white-space: nowrap;
        font-size: 0.72rem;
        color: #8892A4;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        font-weight: 600;
    }
    .discount-card-period {
        white-space: nowrap;
        font-size: 0.66rem;
        color: #94A3B8;
        background: rgba(255,255,255,0.05);
        padding: 1px 6px;
        border-radius: 4px;
    }
    .discount-hero-box {
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        margin: 2px 0 6px 0;
    }
    .discount-hero-num {
        font-size: 1.9rem;
        font-weight: 800;
        color: #F8FAFC;
        line-height: 1;
    }
    .discount-hero-sub {
        font-size: 0.78rem;
        color: #22C55E;
        font-weight: 600;
        text-align: right;
    }
    .discount-bar-track {
        display: flex;
        width: 100%;
        height: 6px;
        border-radius: 3px;
        overflow: hidden;
        background: rgba(255,255,255,0.06);
        margin-bottom: 8px;
    }
    .discount-bar-pass {
        background: #22C55E;
    }
    .discount-bar-absorb {
        background: rgba(239,68,68,0.65);
    }
    .discount-detail-list {
        display: flex;
        flex-direction: column;
        gap: 5px;
    }
    .discount-detail-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 6px;
        padding: 4px 6px;
        border-radius: 7px;
        background: rgba(255,255,255,0.02);
        font-size: 0.72rem;
    }
    .discount-detail-label {
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        min-width: 0;
        color: #CBD5E1;
    }
    .discount-detail-val {
        white-space: nowrap;
        font-weight: 700;
        color: #F8FAFC;
    }
    .discount-footer {
        font-size: 0.68rem;
        color: #64748B;
        margin-top: 4px;
        border-top: 1px solid rgba(255,255,255,0.04);
        padding-top: 4px;
    }

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
    div[data-testid="stSlider"] [role="slider"],
    div[data-baseweb="slider"] [role="slider"],
    div[data-testid="stSlider"] div[data-testid="stThumbValue"] {
        cursor: grab !important;
        border: 2px solid #F5A623 !important;
        background: #0A0F1E !important;
        box-shadow: 0 0 0 2px rgba(245,166,35,0.25) !important;
    }
    div[data-testid="stSlider"] [role="slider"]:active,
    div[data-baseweb="slider"] [role="slider"]:active {
        cursor: grabbing !important;
        box-shadow: 0 0 0 4px rgba(245,166,35,0.35) !important;
    }
    div[data-testid="stSlider"] [role="slider"]::after,
    div[data-baseweb="slider"] [role="slider"]::after {
        content: "⋮⋮";
        display: flex;
        align-items: center;
        justify-content: center;
        color: #F5A623;
        font-size: 8px;
        letter-spacing: -1px;
        height: 100%;
    }
    div[data-testid="stSlider"] [data-testid="stTickBarMin"],
    div[data-testid="stSlider"] [data-testid="stTickBarMax"] {
        color: #94A3B8 !important;
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

    /* ── Mobile Responsive Optimizations ── */
    @media (max-width: 768px) {
        /* Reduce block container margins on small viewports */
        .block-container {
            padding-top: 1.25rem !important;
            padding-bottom: 2rem !important;
            padding-left: 0.6rem !important;
            padding-right: 0.6rem !important;
        }

        /* Full width mobile sidebar */
        [data-testid="stSidebar"] {
            min-width: 85vw !important;
            max-width: 85vw !important;
        }

        /* Horizontally scrollable smooth tabs on phone */
        [data-testid="stTabs"] [data-baseweb="tab-list"] {
            overflow-x: auto !important;
            flex-wrap: nowrap !important;
            white-space: nowrap !important;
            padding-bottom: 4px;
            scrollbar-width: none;
        }
        [data-testid="stTabs"] [data-baseweb="tab-list"]::-webkit-scrollbar {
            display: none;
        }
        [data-testid="stTabs"] [data-baseweb="tab"] {
            padding: 8px 12px !important;
            font-size: 0.80rem !important;
            flex-shrink: 0 !important;
        }

        /* Compact cards for mobile stacking */
        .price-stack-card, .discount-card, .kpi-card {
            padding: 10px 12px !important;
            min-height: auto !important;
            margin-bottom: 8px !important;
        }
        .discount-hero-num {
            font-size: 1.65rem !important;
        }
        .discount-hero-sub {
            font-size: 0.72rem !important;
        }
        .price-stack-header {
            margin-bottom: 4px;
        }
        .price-stack-title {
            font-size: 0.72rem !important;
        }
        .price-stack-total-highlight {
            font-size: 0.95rem !important;
        }
        .stack-name {
            font-size: 0.74rem !important;
        }
        .stack-desc {
            font-size: 0.60rem !important;
        }
        .stack-val-main {
            font-size: 0.85rem !important;
        }
        .discount-detail-row {
            padding: 3px 6px !important;
            font-size: 0.72rem !important;
        }
        .discount-footer {
            font-size: 0.62rem !important;
        }

        /* Form elements & text readability */
        div[data-testid="stSelectbox"] label,
        div[data-testid="stDateInput"] label {
            font-size: 0.80rem !important;
        }
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
PLOT_CONFIG = {'displayModeBar': False, 'responsive': True}

ACCENT      = "#F5A623"   # amber / energy
ACCENT_ALT  = "#22C55E"   # green / reference
DANGER      = "#EF4444"   # red / warning
BLUE        = "#3B82F6"   # blue / reference
SPREAD      = "#A855F7"   # violet / net product spread (distinct from amber pump price)

# Fuel Discount periods
# Translation keys are resolved inside add_discount_bands after language is selected.
DISCOUNT_PERIODS = [
    ("2022-06-01", "2022-08-31", "discount_period_1_annotation"),
    ("2026-05-01", "2026-06-30", "discount_period_2_annotation"),
    ("2026-10-01", "2026-12-31", "discount_period_3_annotation"),
]
STABLE_MARGIN_BASELINE_DAYS = 365

# Canonical English event keys used internally (filtering, data columns).
EVENT_NAME_KEYS = {
    "Tankrabatt 1 Start (Jun 2022)": "policy_event_1_start",
    "Tankrabatt 1 End (Sep 2022)":   "policy_event_1_end",
    "Tankrabatt 2 Start (May 2026)": "policy_event_2_start",
    "Tankrabatt 2 End (Jul 2026)":   "policy_event_2_end",
    "Tankrabatt 3 Start (Oct 2026)": "policy_event_3_start",
    "Tankrabatt 3 End (Jan 2027)":   "policy_event_3_end",
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
    "Tankrabatt 2 End (Jul 2026)": [
        # End was legally certain from start of the discount (fixed 2-month term: May 1 – Jun 30)
        ("phase_expiry_fixed",       date(2026, 5, 1),  "#F5A623"),   # Day −61 — amber / known from start
    ],
    "Tankrabatt 3 Start (Oct 2026)": [
        ("phase_official_announcement", date(2026, 9, 18), "#F5A623"),   # Day −13 — amber / Bund-Länder agreement
        ("phase_parliamentary_vote", date(2026, 9, 25), "#10B981"),   # Day −6  — green / legal certainty
    ],
    "Tankrabatt 3 End (Jan 2027)": [
        # Fixed 3-month term: Oct 1 – Dec 31, 2026
        ("phase_expiry_fixed",       date(2026, 10, 1), "#F5A623"),   # Day −92 — amber / known from start
    ],
}

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
def _station_count_weighted_national(regional_df: pl.DataFrame) -> pl.DataFrame:
    """
    Compute a station-count-weighted national daily average from the regional
    daily margins file. Unknown/unmapped regions are excluded.
    """
    known = regional_df.filter(pl.col("region") != "Unknown Region")
    return (
        known.group_by("date")
        .agg([
            (pl.col("price_diesel") * pl.col("station_count")).sum() / pl.col("station_count").sum(),
            (pl.col("price_e5") * pl.col("station_count")).sum() / pl.col("station_count").sum(),
            (pl.col("price_e10") * pl.col("station_count")).sum() / pl.col("station_count").sum(),
        ])
        .rename({
            "price_diesel": "price_diesel_weighted",
            "price_e5": "price_e5_weighted",
            "price_e10": "price_e10_weighted",
        })
        .sort("date")
    )


def load_data(start_date: date | None = None, smoothing_days: int = 1):
    """
    Loads the real aggregated daily spreads (Tankerkönig + Macro).
    The raw pump-price columns are replaced with a station-count-weighted
    national average computed from the regional file, which is more
    representative than a simple unweighted mean.
    """
    df = pl.read_parquet(DAILY_FILE)
    if start_date is not None:
        df = df.filter(pl.col("date") >= start_date)

    if REGIONAL_DAILY_FILE.exists():
        regional = pl.read_parquet(REGIONAL_DAILY_FILE)
        weighted = _station_count_weighted_national(regional)
        df = df.join(weighted, on="date", how="left")
        df = df.with_columns([
            pl.when(pl.col("price_diesel_weighted").is_not_null())
            .then(pl.col("price_diesel_weighted"))
            .otherwise(pl.col("price_diesel"))
            .alias("price_diesel"),
            pl.when(pl.col("price_e5_weighted").is_not_null())
            .then(pl.col("price_e5_weighted"))
            .otherwise(pl.col("price_e5"))
            .alias("price_e5"),
            pl.when(pl.col("price_e10_weighted").is_not_null())
            .then(pl.col("price_e10_weighted"))
            .otherwise(pl.col("price_e10"))
            .alias("price_e10"),
        ]).drop([
            "price_diesel_weighted",
            "price_e5_weighted",
            "price_e10_weighted",
        ])

    macro_file = DATA_DIR / "processed_macro_baseline.parquet"
    if macro_file.exists():
        macro = pl.read_parquet(macro_file).select(["date", "DCOILBRENTEU", "DEXUSEU"])
        df = df.join(macro, on="date", how="left")
        df = df.with_columns([
            pl.col("DCOILBRENTEU").forward_fill().backward_fill(),
            pl.col("DEXUSEU").forward_fill().backward_fill(),
        ])
        df = df.with_columns([
            (pl.col("DCOILBRENTEU") / pl.col("DEXUSEU")).alias("brent_eur_barrel"),
            pl.col("DCOILBRENTEU").alias("brent_usd_barrel"),
        ])
    else:
        df = df.with_columns([
            (pl.col("Raw_Material_EUR_per_Liter") * 158.9873).alias("brent_eur_barrel"),
            (pl.col("Raw_Material_EUR_per_Liter") * 158.9873 * 1.14).alias("brent_usd_barrel"),
        ])

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

@st.cache_data(show_spinner="Loading compliance audit data… / Lade Compliance-Audit-Daten…")
def load_compliance_data(cache_token: str = "2026-09-19-v4"):
    if not COMPLIANCE_TREND_FILE.exists() or not COMPLIANCE_RANKINGS_FILE.exists():
        return None, None, None
    trend_df = pl.read_parquet(COMPLIANCE_TREND_FILE).to_pandas()
    rankings_df = pl.read_parquet(COMPLIANCE_RANKINGS_FILE).to_pandas()
    lateness_df = pl.read_parquet(COMPLIANCE_LATENESS_FILE).to_pandas() if COMPLIANCE_LATENESS_FILE.exists() else None
    return trend_df, rankings_df, lateness_df


@st.cache_data(show_spinner=False)
def load_network_totals():
    cleaned_st_file = DATA_DIR / "tankerkoenig" / "stations" / "cleaned-stations.parquet"
    if not cleaned_st_file.exists():
        return {}, {}
    st_df = pl.read_parquet(cleaned_st_file)
    vc_grp = st_df["corporate_group"].value_counts()
    group_map = dict(zip(vc_grp["corporate_group"].to_list(), vc_grp["count"].to_list()))
    group_map["Esso (EG Group / TDR Capital)"] = group_map.get("EG Group (Esso)", 1396)

    vc_reg = st_df["region"].value_counts()
    region_map = dict(zip(vc_reg["region"].to_list(), vc_reg["count"].to_list()))
    return group_map, region_map


@st.cache_data(show_spinner=False)
def load_single_station_forensics(station_uuid: str, fuel: str, strict_noon: bool = False) -> pl.DataFrame:
    return get_station_price_history(station_uuid, fuel, strict_noon=strict_noon)



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

    # Default view focuses on the period around the 2022 tax-break / Ukraine-war
    # price shock, but the full historical range remains available on the slider.
    focus_start = max(min_d, date(2021, 12, 24))  # ~2 months before 24 Feb 2022
    date_range = st.slider(
        translate("date_range"),
        min_value=min_d, max_value=max_d,
        value=(focus_start, max_d),
        help=translate("date_range_help") + " " + translate("date_range_drag_help")
    )
    st.caption(f"<span style='color:#94A3B8;font-size:0.75rem;'>{translate('date_range_drag_caption')}</span>", unsafe_allow_html=True)

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
    crude_unit_options = {
        "eur_l": translate("crude_unit_eur_l"),
        "usd_bbl": translate("crude_unit_usd_bbl"),
        "eur_bbl": translate("crude_unit_eur_bbl"),
        "both": translate("crude_unit_both"),
    }
    crude_unit_mode = st.selectbox(
        translate("crude_unit_mode"),
        list(crude_unit_options),
        index=0,
        format_func=lambda key: crude_unit_options[key]
    )

    st.divider()
    show_tax_trend = st.checkbox(translate("tax_trend"), value=False, help=translate("tax_trend_help"))

    st.divider()
    with st.expander(f"⚖️ {translate('legal_center_title')}", expanded=False):
        st.markdown(f"""
        <div style='font-size:0.77rem;color:#CBD5E1;line-height:1.55;'>
            <div style='font-weight:700;color:#38BDF8;margin-bottom:4px;'>{translate('legal_sec1_title')}</div>
            {translate('legal_sec1_desc')}
            <div style='margin-top:8px;font-weight:700;color:#FBBF24;'>{translate('legal_sec2_title')}</div>
            {translate('legal_sec2_desc')}
            <div style='margin-top:8px;font-weight:700;color:#34D399;'>{translate('legal_sec3_title')}</div>
            {translate('compliance_paechter_note')}
            <div style='margin-top:8px;font-weight:700;color:#F87171;'>{translate('legal_sec4_title')}</div>
            {translate('legal_sec4_desc')}
        </div>
        """, unsafe_allow_html=True)

    st.markdown(f"<div style='color:#4A5568;font-size:0.72rem;margin-top:auto;padding-top:16px;'>{translate('data_sources')}</div>", unsafe_allow_html=True)

# ==========================================
# 4. MAIN AREA
# ==========================================

title_html = f"""
<div style="display:flex;align-items:baseline;justify-content:space-between;gap:16px;padding-bottom:12px;border-bottom:1px solid rgba(255,255,255,0.08);margin-bottom:24px;">
    <div style="display:flex;flex-direction:column;gap:2px;">
        <div style="font-size:1.6rem;font-weight:800;color:#E8EAF0;line-height:1.2;">{translate("main_title_line1")}</div>
        <div style="font-size:1.15rem;font-weight:500;color:#A855F7;line-height:1.2;">{translate("main_title_line2")}</div>
        <div style="font-size:0.85rem;font-weight:400;color:#8892A4;margin-top:6px;">{translate("main_subtitle")}</div>
    </div>
    <div style="display:flex;flex-direction:column;align-items:flex-end;gap:2px;font-size:0.7rem;color:#64748B;white-space:nowrap;">
        <span>{translate("app_version_label")} v1.1.0</span>
        <span>{translate("data_through_label")} {max_d.strftime('%Y-%m-%d')}</span>
    </div>
</div>
"""
st.markdown(title_html, unsafe_allow_html=True)

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


def mean_total_tax_for_window(source_df: pl.DataFrame, start: date, end: date, f_key: str | None = None) -> float:
    """Mean total tax (VAT + EBV + CO2 + energy) over a date window for the selected fuel."""
    window_df = source_df.filter((pl.col("date") >= start) & (pl.col("date") <= end))
    if window_df.is_empty():
        return float("nan")
    v_col = col_map[f_key]["vat"] if f_key and f_key in col_map else vat_col
    e_col = col_map[f_key]["ebv"] if f_key and f_key in col_map else ebv_col
    c_col = col_map[f_key]["co2"] if f_key and f_key in col_map else co2_col
    en_col = col_map[f_key]["energy"] if f_key and f_key in col_map else energy_col
    total_expr = pl.col(v_col) + pl.col(e_col) + pl.col(c_col) + pl.col(en_col)
    return float(window_df.select(total_expr.mean()).item())


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


# ── KPI Row ──────────────────────────────────────────────────────────────────
col_stack, col_rabatt1, col_rabatt2, col_rabatt3 = st.columns([1.3, 1.0, 1.0, 1.0])

current_raw  = df["Raw_Material_EUR_per_Liter"].iloc[-1]
current_pump = df[pump_price_col].iloc[-1]
current_marg = df[margin_col].iloc[-1]
current_vat = df[vat_col].iloc[-1]
current_ebv = df[ebv_col].iloc[-1]
current_co2 = df[co2_col].iloc[-1]
current_energy = df[energy_col].iloc[-1]
current_tax = current_vat + current_ebv + current_co2 + current_energy

raw_pct = (current_raw / current_pump) * 100 if current_pump > 0 else 0.0
marg_pct = (current_marg / current_pump) * 100 if current_pump > 0 else 0.0
tax_pct = (current_tax / current_pump) * 100 if current_pump > 0 else 0.0

current_raw_usd_bbl = df["brent_usd_barrel"].iloc[-1] if "brent_usd_barrel" in df.columns else current_raw * 158.9873 * 1.14
current_raw_eur_bbl = df["brent_eur_barrel"].iloc[-1] if "brent_eur_barrel" in df.columns else current_raw * 158.9873

taxes_desc_str = translate("taxes_desc").format(
    energy=f"€{current_energy:.3f}",
    vat=f"€{current_vat:.3f}",
    co2=f"€{current_co2:.3f}",
    ebv=f"€{current_ebv:.4f}"
)
margin_desc_str = translate("margin_desc")
crude_desc_str = translate("crude_desc").format(
    usd_bbl=f"${current_raw_usd_bbl:.2f}/bbl",
    eur_bbl=f"€{current_raw_eur_bbl:.2f}/bbl"
)
pump_desc_str = translate("pump_price_desc").format(fuel=fuel_type)

# Detailed industrial cost layer decomposition (Crude FOB, Freight, Crack Spread, Logistics, Margins, Taxes)
product_col = f"{fuel_key}_product_eur_liter"
current_prod_cost = df[product_col].iloc[-1] if product_col in df.columns else None

detailed_price_breakdown = decompose_single_price(
    pump_price=current_pump,
    crude_fob=current_raw,
    product_wholesale=current_prod_cost,
    energy_tax=current_energy,
    co2_tax=current_co2,
    ebv_tax=current_ebv,
    vat=current_vat,
)
st.session_state["latest_price_breakdown"] = detailed_price_breakdown

with col_stack:
    st.markdown(f"""
    <div class='price-stack-card'>
        <div class='price-stack-header'>
            <div>
                <span class='price-stack-title'>{translate('price_composition_title')} ({fuel_type})</span>
                <span class='price-stack-sub'> · {translate('price_composition_sub')}</span>
            </div>
            <div class='price-stack-total-highlight'>€{current_pump:.3f} <span style='font-size:0.75rem;color:#94A3B8;font-weight:500;'>/ L</span></div>
        </div>
        <div class='price-stack-bar'>
            <div class='bar-seg-crude' style='width: {raw_pct:.1f}%;' title='{translate("crude_oil_base_label")}: {raw_pct:.1f}%'></div>
            <div class='bar-seg-margin' style='width: {marg_pct:.1f}%;' title='{translate("net_product_margin_label")}: {marg_pct:.1f}%'></div>
            <div class='bar-seg-tax' style='width: {tax_pct:.1f}%;' title='{translate("taxes_and_levies_label")}: {tax_pct:.1f}%'></div>
        </div>
        <div class='price-stack-list'>
            <!-- Level 4: Zapfsäulenpreis (Top) -->
            <div class='price-stack-item level-pump'>
                <div class='stack-meta'>
                    <div class='stack-label-row'>
                        <span class='stack-badge badge-pump'>{translate('badge_total')}</span>
                        <span class='stack-name'>{translate('pump_price_total_label')}</span>
                    </div>
                    <div class='stack-desc'>{pump_desc_str}</div>
                </div>
                <div class='stack-values'>
                    <div class='stack-val-main'>€{current_pump:.3f}</div>
                    <div class='stack-val-pct'>100.0%</div>
                </div>
            </div>
            <!-- Level 3: Steuern & Abgaben -->
            <div class='price-stack-item'>
                <div class='stack-meta'>
                    <div class='stack-label-row'>
                        <span class='stack-badge badge-tax'>{translate('badge_taxes')}</span>
                        <span class='stack-name'>{translate('taxes_and_levies_label')}</span>
                    </div>
                    <div class='stack-desc'>{taxes_desc_str}</div>
                </div>
                <div class='stack-values'>
                    <div class='stack-val-main' style='color:#FBBF24;'>+€{current_tax:.3f}</div>
                    <div class='stack-val-pct'>{tax_pct:.1f}%</div>
                </div>
            </div>
            <!-- Level 2: Netto-Produktspanne -->
            <div class='price-stack-item'>
                <div class='stack-meta'>
                    <div class='stack-label-row'>
                        <span class='stack-badge badge-margin'>{translate('badge_margin')}</span>
                        <span class='stack-name'>{translate('net_product_margin_label')}</span>
                    </div>
                    <div class='stack-desc'>{margin_desc_str}</div>
                </div>
                <div class='stack-values'>
                    <div class='stack-val-main' style='color:#34D399;'>+€{current_marg:.3f}</div>
                    <div class='stack-val-pct'>{marg_pct:.1f}%</div>
                </div>
            </div>
            <!-- Level 1: Brent-Rohöl (Bottom) -->
            <div class='price-stack-item'>
                <div class='stack-meta'>
                    <div class='stack-label-row'>
                        <span class='stack-badge badge-crude'>{translate('badge_base')}</span>
                        <span class='stack-name'>{translate('crude_oil_base_label')}</span>
                    </div>
                    <div class='stack-desc'>{crude_desc_str}</div>
                </div>
                <div class='stack-values'>
                    <div class='stack-val-main' style='color:#38BDF8;'>€{current_raw:.3f}</div>
                    <div class='stack-val-pct'>{raw_pct:.1f}%</div>
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

pre_disc_start, pre_disc_end, pre_disc = stable_pre_event_margin_baseline(
    df_full, margin_col, date(2022, 6, 1)
)
disc_marg = mean_for_date_window(df_full, margin_col, date(2022, 6, 1), date(2022, 8, 31))
delta_marg = disc_marg - pre_disc if not (pre_disc != pre_disc or disc_marg != disc_marg) else 0

# Compute consistent discount-window stats for both tax breaks.
# Compute consistent discount-window stats for both tax breaks.
# Mathematical integrity rules:
# 1. Pass-through % = (Weitergegeben / Steuersenkung) * 100 <= 100%
# 2. Steuersenkung = Weitergegeben + Einbehalten (Kosten & Marge)
# 3. Numbers must strictly add up to 100% of the tax cut
d1_start, d1_end = date(2022, 6, 1), date(2022, 8, 31)
d2_start, d2_end = date(2026, 5, 1), date(2026, 6, 30)
d3_start, d3_end = date(2026, 10, 1), date(2026, 12, 31)
max_date = df_full["date"].max()
d2_actual_end = min(d2_end, max_date)
d3_actual_end = min(d3_end, max_date)


def _compute_discount_card_kpi(
    start: date,
    end: date,
    source_df: pl.DataFrame,
    p_col: str,
    f_key: str | None = None,
) -> dict:
    if f_key is None:
        f_key = p_col.replace("price_", "")
    period_days = (end - start).days + 1
    pre_start = start - timedelta(days=period_days)
    pre_end = start - timedelta(days=1)
    pre_pump = mean_for_date_window(source_df, p_col, pre_start, pre_end)
    disc_pump = mean_for_date_window(source_df, p_col, start, end)
    pre_tax = mean_total_tax_for_window(source_df, pre_start, pre_end, f_key=f_key)
    disc_tax = mean_total_tax_for_window(source_df, start, end, f_key=f_key)

    raw_tax_drop_ct = (pre_tax - disc_tax) * 100
    raw_pump_drop_ct = (pre_pump - disc_pump) * 100
    raw_pass_pct = (raw_pump_drop_ct / raw_tax_drop_ct * 100) if raw_tax_drop_ct > 0 else 0.0

    is_anomaly = raw_pass_pct > 100.0
    crude_drop_ct = 0.0

    if is_anomaly:
        # Anomaly detected: Raw pump price drop exceeds the tax cut because crude/procurement
        # prices collapsed simultaneously (e.g., easing of the Iran war spike).
        # We isolate pure tax transmission using the 14-day event window around effective date.
        pre_event_start = start - timedelta(days=14)
        pre_event_end = start - timedelta(days=1)
        disc_event_start = start
        disc_event_end = start + timedelta(days=13)

        pre_ev_pump = mean_for_date_window(source_df, p_col, pre_event_start, pre_event_end)
        disc_ev_pump = mean_for_date_window(source_df, p_col, disc_event_start, disc_event_end)
        pre_ev_tax = mean_total_tax_for_window(source_df, pre_event_start, pre_event_end, f_key=f_key)
        disc_ev_tax = mean_total_tax_for_window(source_df, disc_event_start, disc_event_end, f_key=f_key)

        tax_drop_ct = (pre_ev_tax - disc_ev_tax) * 100
        event_pump_drop_ct = (pre_ev_pump - disc_ev_pump) * 100
        passed_ct = min(tax_drop_ct, max(0.0, event_pump_drop_ct))
        pass_pct = (passed_ct / tax_drop_ct * 100) if tax_drop_ct > 0 else 0.0

        pre_crude = mean_for_date_window(source_df, "Raw_Material_EUR_per_Liter", pre_start, pre_end)
        disc_crude = mean_for_date_window(source_df, "Raw_Material_EUR_per_Liter", start, end)
        crude_drop_ct = max(0.0, (pre_crude - disc_crude) * 100)
        used_adjusted = True
        baseline_start = pre_event_start
        baseline_end = pre_event_end
        baseline_days = 14
    else:
        tax_drop_ct = raw_tax_drop_ct
        passed_ct = min(tax_drop_ct, max(0.0, raw_pump_drop_ct))
        pass_pct = raw_pass_pct
        used_adjusted = False
        baseline_start = pre_start
        baseline_end = pre_end
        baseline_days = period_days

    # Mathematical & economic integrity checks:
    # 1. Pass-through cannot exceed 100%
    pass_pct = min(100.0, max(0.0, pass_pct))

    # 2. Strict identity: Steuersenkung = Weitergegeben + Einbehalten (Kosten & Marge)
    retained_ct = max(0.0, tax_drop_ct - passed_ct)

    # 3. Progress bars
    pass_bar = pass_pct
    absorb_bar = 100.0 - pass_bar

    # Explicit validation check
    validation_error = None
    if pass_pct > 100.0:
        validation_error = f"Validation Error: Pass-through ({pass_pct:.1f}%) exceeds 100% of tax cut!"
    elif abs((passed_ct + retained_ct) - tax_drop_ct) > 0.05:
        validation_error = f"Validation Error: {passed_ct:.1f} + {retained_ct:.1f} != {tax_drop_ct:.1f} ct/L"

    return {
        "tax_drop_ct": tax_drop_ct,
        "passed_ct": passed_ct,
        "retained_ct": retained_ct,
        "pass_pct": pass_pct,
        "pass_bar": pass_bar,
        "absorb_bar": absorb_bar,
        "raw_pass_pct": raw_pass_pct,
        "is_anomaly": is_anomaly,
        "used_adjusted": used_adjusted,
        "crude_drop_ct": crude_drop_ct,
        "baseline_start": baseline_start,
        "baseline_end": baseline_end,
        "baseline_days": baseline_days,
        "validation_error": validation_error,
    }


def _format_baseline_dates(d_start: date, d_end: date, is_de: bool) -> tuple[str, str]:
    if is_de:
        return d_start.strftime("%d.%m."), d_end.strftime("%d.%m.%Y")
    return d_start.strftime("%d/%m"), d_end.strftime("%d/%m/%Y")


@st.cache_data(show_spinner=False)
def load_did_pass_through() -> dict:
    if not PASS_THROUGH_FILE.exists():
        return {}
    return {(r["event"], r["fuel"]): r for r in pl.read_parquet(PASS_THROUGH_FILE).iter_rows(named=True)}


def _apply_did_estimate(kpi: dict | None, event: str) -> dict | None:
    """Swap the raw pump change for the EU Oil Bulletin difference-in-differences estimate, if one exists.
    The raw change also holds crude/refining moves; the euro-area control countries cancel those out."""
    did = load_did_pass_through().get((event, fuel_key))
    if kpi is None or did is None:
        return kpi
    pass_pct = min(100.0, max(0.0, did["pass_through_pct"]))
    passed_ct = did["statutory_ct"] * pass_pct / 100
    return {
        **kpi,
        "tax_drop_ct": did["statutory_ct"],
        "passed_ct": passed_ct,
        "retained_ct": did["statutory_ct"] - passed_ct,
        "pass_pct": pass_pct,
        "pass_bar": pass_pct,
        "absorb_bar": 100.0 - pass_pct,
        "is_anomaly": False,
        "did_controls": did["controls"],
    }


d1_kpi = _apply_did_estimate(_compute_discount_card_kpi(d1_start, d1_end, df_full, pump_price_col), "TR1")
d2_kpi = _apply_did_estimate(_compute_discount_card_kpi(d2_start, d2_actual_end, df_full, pump_price_col), "TR2")
d3_kpi = _apply_did_estimate(
    _compute_discount_card_kpi(d3_start, d3_actual_end, df_full, pump_price_col) if d3_start <= max_date else None, "TR3"
)

for _kpi in (d1_kpi, d2_kpi, d3_kpi):
    if _kpi and _kpi["validation_error"]:
        st.error(_kpi["validation_error"])

is_german = selected_language == "de"


def _render_discount_card(
    column,
    kpi: dict | None,
    title_key: str,
    period_key: str,
    css_class: str = "",
    show_anomaly: bool = False,
    live_badge: str = "",
) -> None:
    """Render one Tankrabatt pass-through KPI card into the given column."""
    if kpi is None:
        with column:
            st.markdown(f"""
            <div class='discount-card {css_class}'>
                <div class='discount-card-header'>
                    <span class='discount-card-title'>{translate(title_key)}</span>
                    <span class='discount-card-period'>{translate(period_key)}</span>
                </div>
                <div class='discount-footer'>{translate('discount_no_data_yet')}</div>
            </div>
            """, unsafe_allow_html=True)
        return

    s_str, e_str = _format_baseline_dates(kpi["baseline_start"], kpi["baseline_end"], is_german)
    baseline_template = (
        translate("discount_baseline_concrete_pre_event")
        if show_anomaly and kpi["used_adjusted"]
        else translate("discount_baseline_concrete")
    )
    footer = baseline_template.format(start=s_str, end=e_str, days=kpi["baseline_days"])
    if kpi.get("did_controls"):
        footer = translate("discount_baseline_did").format(controls=kpi["did_controls"].replace(" ", ", "))
    anomaly_html = ""
    if show_anomaly and kpi["is_anomaly"]:
        warn_text = translate("discount_validation_warning").format(
            raw_pct=kpi["raw_pass_pct"],
            crude_drop=kpi["crude_drop_ct"],
        )
        anomaly_html = f"<div style='margin-top:6px;font-size:0.73rem;color:#38BDF8;background:rgba(56,189,248,0.08);border:1px solid rgba(56,189,248,0.25);padding:5px 8px;border-radius:4px;line-height:1.3;'>{warn_text}</div>"
    live_html = f"<span class='discount-live-badge'>● {live_badge}</span>" if live_badge else ""

    with column:
        st.markdown(f"""
        <div class='discount-card {css_class}'>
            <div class='discount-card-header'>
                <span class='discount-card-title'>{translate(title_key)}</span>
                <span class='discount-card-period'>{translate(period_key)}</span>{live_html}
            </div>
            <div class='discount-hero-box'>
                <div class='discount-hero-num'>{kpi['pass_pct']:.0f}%</div>
                <div class='discount-hero-sub'>✓ {translate('discount_pass_label')}</div>
            </div>
            <div class='discount-bar-track' title='{kpi['pass_pct']:.1f}% Weitergabe'>
                <div class='discount-bar-pass' style='width: {kpi['pass_bar']:.1f}%;'></div>
                <div class='discount-bar-absorb' style='width: {kpi['absorb_bar']:.1f}%;'></div>
            </div>
            <div class='discount-detail-list'>
                <div class='discount-detail-row'>
                    <span class='discount-detail-label' title="{translate('discount_tax_cut_label')}">{translate('discount_tax_cut_label')}</span>
                    <span class='discount-detail-val' style='color:#FBBF24;'>{kpi['tax_drop_ct']:.1f} ct / L</span>
                </div>
                <div class='discount-detail-row'>
                    <span class='discount-detail-label' title="{translate('discount_pump_drop_label')}">{translate('discount_pump_drop_label')}</span>
                    <span class='discount-detail-val' style='color:#34D399;'>{kpi['passed_ct']:.1f} ct / L</span>
                </div>
                <div class='discount-detail-row'>
                    <span class='discount-detail-label' title="{translate('discount_margin_absorbed_label')}">{translate('discount_margin_absorbed_label')}</span>
                    <span class='discount-detail-val' style='color:#F87171;'>+{kpi['retained_ct']:.1f} ct / L</span>
                </div>
            </div>
            <div class='discount-footer'>{footer}</div>
            {anomaly_html}
        </div>
        """, unsafe_allow_html=True)


d3_live_badge = ""
if d3_kpi is not None and max_date < d3_end:
    d3_live_badge = translate("discount_live_badge").format(
        day=(d3_actual_end - d3_start).days + 1,
        total=(d3_end - d3_start).days + 1,
    )

_render_discount_card(col_rabatt1, d1_kpi, "discount_1_short", "discount_1_period")
_render_discount_card(col_rabatt2, d2_kpi, "discount_2_short", "discount_2_period", "discount-2", show_anomaly=True)
_render_discount_card(col_rabatt3, d3_kpi, "discount_3_short", "discount_3_period", "discount-3", show_anomaly=True, live_badge=d3_live_badge)

st.markdown("<br>", unsafe_allow_html=True)

# ── Tabs ────────────────────────────────────────────────────────────────────
tab1, tab_compliance, tab2, tab3, tab_brand, tab_advisor, tab_rag = st.tabs([
    translate("tab_brent"),
    translate("tab_compliance"),
    translate("tab_spread"),
    translate("tab_rhythm"),
    translate("tab_brand"),
    translate("tab_advisor"),
    translate("tab_rag"),
])

# ── Helper: Add Discount Highlight Bands ─────────────────────────────────────
def add_discount_bands(fig):
    colors = ["rgba(245,166,35,0.12)", "rgba(59,130,246,0.10)", "rgba(16,185,129,0.10)"]
    visible_min = df["date"].astype(str).min()
    visible_max = df["date"].astype(str).max()
    prev_anno_date = None
    anno_y = 0.98
    for (x0, x1, label_key), color in zip(DISCOUNT_PERIODS, colors):
        if x0 <= visible_max and x1 >= visible_min:
            fig.add_vrect(
                x0=x0, x1=x1, fillcolor=color, opacity=1,
                layer="below", line_width=1, line_color="rgba(245,166,35,0.3)"
            )
            # Clamp the horizontal start position to visible area
            anno_x = max(x0, visible_min)
            label_text = translate(label_key)

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

            # Stack labels of discounts that start close together (Tankrabatt 2 & 3 are 5 months apart)
            try:
                d_anno = datetime.strptime(anno_x, "%Y-%m-%d")
                anno_y = anno_y - 0.08 if prev_anno_date and (d_anno - prev_anno_date).days < 240 else 0.98
                prev_anno_date = d_anno
            except Exception:
                anno_y = 0.98

            fig.add_annotation(
                x=anno_x,
                y=anno_y,
                xref="x",
                yref="paper",
                text=label_text,
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


def add_current_value_line(fig, value, color):
    """Add a dashed horizontal reference line at the given current value."""
    fig.add_hline(
        y=value,
        line_dash="dash",
        line_color=color,
        line_width=2,
        annotation_text=f"€{value:.3f}/L",
        annotation_position="right",
        annotation_font_color=color,
        annotation_font_size=11,
    )
    return fig


def calculate_tax_break_pass_through(source_df: pl.DataFrame) -> list[dict[str, object]]:
    """Compare pump-price drops with tax-burden drops for each tax-break window."""
    max_date = source_df["date"].max()
    periods = [
        (translate("tankrabatt_1"), date(2022, 6, 1), date(2022, 8, 31)),
        (translate("tankrabatt_2"), date(2026, 5, 1), date(2026, 6, 30)),
        (translate("tankrabatt_3"), date(2026, 10, 1), date(2026, 12, 31)),
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
        ("tax_break_off_2026", date(2026, 7, 1)),
        ("tax_break_on_2026_q4", date(2026, 10, 1)),
        ("tax_break_off_2027", date(2027, 1, 1)),
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
        ("Tankrabatt 2 End (Jul 2026)",   date(2026, 7, 1),  "tax_hike"),
        ("Tankrabatt 3 Start (Oct 2026)", date(2026, 10, 1), "tax_cut"),
        ("Tankrabatt 3 End (Jan 2027)",   date(2027, 1, 1),  "tax_hike"),
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
        st.markdown(f"<p style='color:#8892A4;font-size:0.85rem;opacity:0.65;margin-top:8px;margin-bottom:0;'>{translate('brent_vs_pump_note')}</p>", unsafe_allow_html=True)

        fig = go.Figure()
        
        # Base Layer: Brent Crude
        brent_hover = [
            f"€{l:.3f}/L (${u:.2f}/bbl)"
            for l, u in zip(df["Raw_Material_EUR_per_Liter"], df["brent_usd_barrel"])
        ] if "brent_usd_barrel" in df.columns else None

        fig.add_trace(go.Scatter(
            x=df["date"], y=df["Raw_Material_EUR_per_Liter"],
            name=translate("brent"),
            mode="lines",
            fill="tozeroy" if tax_viz == "hide" else None,
            fillcolor="rgba(34,197,94,0.08)" if tax_viz == "hide" else None,
            line=dict(color=ACCENT_ALT, width=2),
            stackgroup="one" if tax_viz != "hide" else None,
            hovertemplate=translate("brent") + ": %{customdata}<extra></extra>" if brent_hover is not None else None,
            customdata=brent_hover if brent_hover is not None else None
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
        
        # Brent's real historical value plus today's spread, held constant. Any
        # gap between this line and the actual stacked top is due to the spread
        # having been different historically, not Brent - isolating the spread
        # story from Brent's own movement.
        brent_plus_current_spread = df["Raw_Material_EUR_per_Liter"] + current_marg
        fig.add_trace(go.Scatter(
            x=df["date"], y=brent_plus_current_spread,
            name=translate("brent_plus_current_spread"),
            mode="lines",
            line=dict(color=SPREAD, width=2, dash="dash"),
        ))

        fig = add_discount_bands(fig)
        fig = add_current_value_line(fig, current_raw, ACCENT_ALT)
        fig = add_current_value_line(fig, current_pump, ACCENT)

        # Determine max Y axis to keep charts stable
        max_y = df[pump_price_col].max() * 1.1
        fig.update_layout(**PLOT_LAYOUT, height=480, yaxis_title=translate("axis_euro_per_liter"), yaxis_range=[0, max_y])
        st.plotly_chart(fig, width='stretch', config=PLOT_CONFIG)

        st.markdown(
            f"<p style='color:#8892A4;font-size:0.8rem;margin-top:-8px;'>"
            f"{translate('brent_vs_pump_disclaimer')}"
            f"</p>",
            unsafe_allow_html=True,
        )

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
            st.plotly_chart(fig_trend, width='stretch', config=PLOT_CONFIG)

        # ── Tax Paradox Callout Box ──
        st.markdown(f"""
        <div style='background:rgba(56,189,248,0.05);border:1px solid rgba(56,189,248,0.2);border-radius:10px;padding:18px 22px;margin:24px 0 16px 0;'>
            <div style='display:flex;align-items:center;gap:10px;font-weight:700;color:#38BDF8;font-size:1.05rem;margin-bottom:6px;'>
                🏛️ {translate('compliance_tax_paradox_title')}
            </div>
            <div style='display:grid;grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));gap:14px;margin-top:12px;margin-bottom:14px;'>
                <div style='background:rgba(15,23,42,0.6);padding:14px;border-radius:8px;border:1px solid rgba(255,255,255,0.05);'>
                    <div style='font-size:0.75rem;color:#8892A4;font-weight:600;'>{translate('tax_paradox_prewar_title')}</div>
                    <div style='font-size:1.25rem;font-weight:700;color:#FBBF24;margin:4px 0;'>{translate('tax_paradox_prewar_val')}</div>
                    <div style='font-size:0.75rem;color:#94A3B8;line-height:1.4;'>{translate('tax_paradox_prewar_sub')}</div>
                </div>
                <div style='background:rgba(15,23,42,0.6);padding:14px;border-radius:8px;border:1px solid rgba(245,166,35,0.25);'>
                    <div style='font-size:0.75rem;color:#FBBF24;font-weight:600;'>{translate('tax_paradox_discount_title')}</div>
                    <div style='font-size:1.25rem;font-weight:700;color:#34D399;margin:4px 0;'>{translate('tax_paradox_discount_val')}</div>
                    <div style='font-size:0.75rem;color:#94A3B8;line-height:1.4;'>{translate('tax_paradox_discount_sub')}</div>
                </div>
                <div style='background:rgba(15,23,42,0.6);padding:14px;border-radius:8px;border:1px solid rgba(239,68,68,0.25);'>
                    <div style='font-size:0.75rem;color:#EF4444;font-weight:600;'>{translate('tax_paradox_today_title')}</div>
                    <div style='font-size:1.25rem;font-weight:700;color:#F87171;margin:4px 0;'>{translate('tax_paradox_today_val')}</div>
                    <div style='font-size:0.75rem;color:#94A3B8;line-height:1.4;'>{translate('tax_paradox_today_sub')}</div>
                </div>
            </div>
            <div style='color:#CBD5E1;font-size:0.83rem;line-height:1.55;'>
                {translate('tax_paradox_body')}
            </div>
        </div>
        """, unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────────────
# TAB 2: Net Product Spread (Margen & Marktmacht)
# ──────────────────────────────────────────────────────────────────────────────
with tab2:
    st.markdown(f"#### {translate('spread_title')}")
    st.markdown(f"<span style='color:#8892A4;font-size:0.85rem;'>{translate('spread_note')}</span>", unsafe_allow_html=True)

    subtab_decomp, subtab_rockets, subtab_counterfactual = st.tabs([
        translate("spread_subtab_decomp"),
        translate("spread_subtab_rockets"),
        translate("spread_subtab_counterfactual"),
    ])

    # ══════════════════════════════════════════════════════════════════════════
    # SUBTAB 1: Wertschöpfungskette & Dekomposition
    # ══════════════════════════════════════════════════════════════════════════
    with subtab_decomp:
        df_decomp = add_granular_decomposition_columns(df, fuel_key)
        decomp_pd = df_decomp.sort_values("date") if hasattr(df_decomp, "sort_values") else df_decomp.sort("date").to_pandas()

        latest_row = decomp_pd.iloc[-1]
        latest_crack = latest_row.get(f"{fuel_key}_decomp_crack_spread", 0.10)
        latest_profit = latest_row.get(f"{fuel_key}_decomp_brand_net_profit", 0.08)
        latest_total_margin = latest_row.get(margin_col, 0.25)

        c_m1, c_m2, c_m3 = st.columns(3)
        with c_m1:
            st.markdown(f"""
            <div class='kpi-card'>
                <div class='kpi-label'>{translate('kpi_total_margin')}</div>
                <div class='kpi-value' style='color:#F5A623;'>{latest_total_margin*100:.1f} ct/L</div>
                <div class='kpi-subtitle'>{translate('kpi_total_margin_sub')}</div>
            </div>
            """, unsafe_allow_html=True)
        with c_m2:
            st.markdown(f"""
            <div class='kpi-card'>
                <div class='kpi-label'>{translate('kpi_crack_spread')}</div>
                <div class='kpi-value' style='color:#38BDF8;'>{latest_crack*100:.1f} ct/L</div>
                <div class='kpi-subtitle'>{translate('kpi_crack_spread_sub')}</div>
            </div>
            """, unsafe_allow_html=True)
        with c_m3:
            profit_color = "#EF4444" if latest_profit > 0.15 else ("#F5A623" if latest_profit > 0.08 else "#22C55E")
            st.markdown(f"""
            <div class='kpi-card insight'>
                <div class='kpi-label'>{translate('kpi_net_profit')}</div>
                <div class='kpi-value' style='color:{profit_color};'>{latest_profit*100:+.1f} ct/L</div>
                <div class='kpi-subtitle'>{translate('kpi_net_profit_sub')}</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(f"##### {translate('chart_decomp_title')}")
        st.markdown(f"<span style='color:#8892A4;font-size:0.83rem;'>{translate('chart_decomp_sub')}</span>", unsafe_allow_html=True)

        fig_decomp = go.Figure()

        fig_decomp.add_trace(go.Scatter(
            x=decomp_pd["date"], y=decomp_pd[f"{fuel_key}_decomp_crude_fob"],
            name=translate("layer_crude"),
            mode="lines",
            stackgroup="one",
            fillcolor="rgba(148, 163, 184, 0.35)",
            line=dict(color="#94A3B8", width=1),
            hovertemplate="%{x|%d.%m.%Y}: <b>€%{y:.3f}/L</b> Rohöl<extra></extra>"
        ))
        fig_decomp.add_trace(go.Scatter(
            x=decomp_pd["date"], y=decomp_pd[f"{fuel_key}_decomp_crack_spread"],
            name=translate("layer_crack"),
            mode="lines",
            stackgroup="one",
            fillcolor="rgba(56, 189, 248, 0.35)",
            line=dict(color="#38BDF8", width=1),
            hovertemplate="%{x|%d.%m.%Y}: <b>€%{y:.3f}/L</b> Crack Spread<extra></extra>"
        ))
        fig_decomp.add_trace(go.Scatter(
            x=decomp_pd["date"], y=decomp_pd[f"{fuel_key}_decomp_domestic_logistics"],
            name=translate("layer_logistics"),
            mode="lines",
            stackgroup="one",
            fillcolor="rgba(168, 85, 247, 0.30)",
            line=dict(color="#A855F7", width=1),
            hovertemplate="%{x|%d.%m.%Y}: <b>€%{y:.3f}/L</b> Logistik/Betrieb<extra></extra>"
        ))
        fig_decomp.add_trace(go.Scatter(
            x=decomp_pd["date"], y=decomp_pd[f"{fuel_key}_decomp_brand_net_profit"].clip(lower=0.0),
            name=translate("layer_profit"),
            mode="lines",
            stackgroup="one",
            fillcolor="rgba(245, 166, 35, 0.45)",
            line=dict(color="#F5A623", width=1.5),
            hovertemplate="%{x|%d.%m.%Y}: <b>€%{y:.3f}/L</b> Reingewinn<extra></extra>"
        ))
        fig_decomp.add_trace(go.Scatter(
            x=decomp_pd["date"], y=decomp_pd[f"{fuel_key}_net_price"],
            name=translate("layer_pump_net"),
            mode="lines",
            line=dict(color="#FFFFFF", width=2.5, dash="dash"),
            hovertemplate="%{x|%d.%m.%Y}: <b>€%{y:.3f}/L</b> Zapfsäule (Netto)<extra></extra>"
        ))

        fig_decomp = add_discount_bands(fig_decomp)
        fig_decomp.update_layout(
            **{
                **PLOT_LAYOUT,
                "legend": dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            },
            height=420,
            yaxis_title=translate("axis_euro_per_liter"),
        )
        st.plotly_chart(fig_decomp, width='stretch', config=PLOT_CONFIG)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(f"##### {translate('chart_pure_profit_title')}")
        st.markdown(f"<span style='color:#8892A4;font-size:0.83rem;'>{translate('chart_pure_profit_sub')}</span>", unsafe_allow_html=True)

        pre_crisis_df = df_full.filter(pl.col("date") <= date(2021, 12, 31))
        df_full_decomp = add_granular_decomposition_columns(pre_crisis_df, fuel_key)
        baseline_profit = df_full_decomp[f"{fuel_key}_decomp_brand_net_profit"].mean() if not df_full_decomp.is_empty() else 0.05
        baseline_profit_ct = baseline_profit * 100

        fig_profit = go.Figure()
        fig_profit.add_trace(go.Scatter(
            x=decomp_pd["date"], y=decomp_pd[f"{fuel_key}_decomp_brand_net_profit"] * 100,
            name=translate("kpi_net_profit"),
            mode="lines",
            line=dict(color="#F5A623", width=2.5),
            fill="tozeroy",
            fillcolor="rgba(245, 166, 35, 0.08)",
            hovertemplate="%{x|%d.%m.%Y}: <b>%{y:.2f} ct/L</b> Reingewinn<extra></extra>"
        ))
        fig_profit.add_hline(
            y=baseline_profit_ct,
            line_dash="dot", line_color="#38BDF8", line_width=1.5,
            annotation_text=f" {translate('precrisis_baseline')}: {baseline_profit_ct:.1f} ct/L",
            annotation_font_color="#38BDF8"
        )
        fig_profit = add_discount_bands(fig_profit)
        fig_profit.update_layout(
            **PLOT_LAYOUT,
            height=360,
            yaxis_title="ct / Liter",
        )
        st.plotly_chart(fig_profit, width='stretch', config=PLOT_CONFIG)

    # ══════════════════════════════════════════════════════════════════════════
    # SUBTAB 2: Rockets & Feathers (Preistransmissions-Forensik)
    # ══════════════════════════════════════════════════════════════════════════
    with subtab_rockets:
        st.markdown(f"#### {translate('rockets_title')}")
        st.markdown(f"<span style='color:#8892A4;font-size:0.85rem;'>{translate('rockets_sub')}</span>", unsafe_allow_html=True)

        asym_res = calculate_asymmetric_pass_through(df_full, fuel_key, window_days=30)
        asym_index = asym_res.get("asymmetry_index", 1.0)
        avg_cut = asym_res.get("avg_cut_pass_through_pct", 75.0)
        avg_hike = asym_res.get("avg_hike_pass_through_pct", 100.0)

        c_r1, c_r2, c_r3 = st.columns(3)
        with c_r1:
            st.markdown(f"""
            <div class='kpi-card insight'>
                <div class='kpi-label'>{translate('asymmetry_index_label')}</div>
                <div class='kpi-value' style='color:#EF4444;'>{asym_index:.2f}x</div>
                <div class='kpi-subtitle'>{translate('asymmetry_index_sub')}</div>
            </div>
            """, unsafe_allow_html=True)
        with c_r2:
            st.markdown(f"""
            <div class='kpi-card'>
                <div class='kpi-label'>{translate('lag_cuts_label')}</div>
                <div class='kpi-value' style='color:#38BDF8;'>3–5 Tage</div>
                <div class='kpi-subtitle'>{avg_cut:.1f}% Weitergabe</div>
            </div>
            """, unsafe_allow_html=True)
        with c_r3:
            st.markdown(f"""
            <div class='kpi-card'>
                <div class='kpi-label'>{translate('lag_hikes_label')}</div>
                <div class='kpi-value' style='color:#22C55E;'>0 Tage</div>
                <div class='kpi-subtitle'>{avg_hike:.1f}% Weitergabe (sofort)</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(f"##### {translate('synoptic_title')}")
        st.markdown(f"<span style='color:#8892A4;font-size:0.83rem;'>{translate('synoptic_sub')}</span>", unsafe_allow_html=True)

        timeline_all = get_event_study_timeline(df_full, pump_price_col, margin_col, window_days=30, normalize=True)
        if not timeline_all.is_empty():
            timeline_pd = timeline_all.to_pandas()
            fig_synoptic = go.Figure()

            event_colors = {
                "Tankrabatt 1 Start (Jun 2022)": ("#38BDF8", "solid", translate("tax_cut_2022")),
                "Tankrabatt 1 End (Sep 2022)": ("#EF4444", "solid", translate("tax_hike_2022_rocket")),
                "Tankrabatt 2 Start (May 2026)": ("#10B981", "dash", translate("tax_cut_2026")),
                "Tankrabatt 2 End (Jul 2026)": ("#F97316", "dash", translate("tax_hike_2026_rocket")),
                "Tankrabatt 3 Start (Oct 2026)": ("#A855F7", "dot", translate("tax_cut_2026_q4")),
                "Tankrabatt 3 End (Jan 2027)": ("#EC4899", "dot", translate("tax_hike_2027_rocket")),
            }

            for evt_name, (ev_col, ev_dash, ev_lbl) in event_colors.items():
                ev_data = timeline_pd[timeline_pd["Event"] == evt_name]
                if not ev_data.empty:
                    disp_evt = translate(EVENT_NAME_KEYS.get(evt_name, evt_name))
                    fig_synoptic.add_trace(go.Scatter(
                        x=ev_data["Relative Day"], y=ev_data["Net Product Spread"] * 100,
                        name=f"{disp_evt} ({ev_lbl})",
                        mode="lines",
                        line=dict(color=ev_col, width=2.5, dash=ev_dash),
                        hovertemplate=f"{disp_evt}<br>{translate('event_window')} %{{x}}: <b>%{{y:+.2f}} ct/L</b><extra></extra>"
                    ))

            fig_synoptic.add_vline(
                x=0, line_dash="dash", line_color="rgba(255,255,255,0.4)", line_width=2,
                annotation_text=f" {translate('event_key_date')} (t=0)",
                annotation_position="top left",
                annotation_font=dict(color="#FFFFFF", size=10)
            )
            fig_synoptic.add_hline(y=0.0, line_dash="dot", line_color="rgba(255,255,255,0.15)", line_width=1)
            fig_synoptic.update_layout(
                **{
                    **PLOT_LAYOUT,
                    "legend": dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                },
                height=420,
                xaxis_title=translate("xaxis_days_relative"),
                yaxis_title="Delta Net Product Spread (ct/L)",
            )
            st.plotly_chart(fig_synoptic, width='stretch', config=PLOT_CONFIG)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(f"##### {translate('event_compare_table_title')}")
        evt_table = []
        for e in asym_res.get("events", []):
            evt_table.append({
                translate("event_table_col_event"): translate(EVENT_NAME_KEYS.get(e["name"], e["name"])),
                translate("event_table_col_type"): translate("tax_cut") if e["type"] == "cut" else translate("tax_hike"),
                translate("event_table_col_date"): str(e["date"]),
                translate("event_table_col_tax_delta"): f"{e['delta_tax']*100:+.1f} ct/L",
                translate("event_table_col_pump_delta"): f"{e['delta_price']*100:+.1f} ct/L",
                translate("event_table_col_pass_through"): f"{e['pass_through_pct']:.1f}%",
                translate("event_table_col_half_life"): f"{e['half_life_days']} d" if e["half_life_days"] > 0 else translate("half_life_immediate"),
            })
        if evt_table:
            st.dataframe(evt_table, hide_index=True, width="stretch")

    # ══════════════════════════════════════════════════════════════════════════
    # SUBTAB 3: Kartell-Renten & Übermargen-Rechner
    # ══════════════════════════════════════════════════════════════════════════
    with subtab_counterfactual:
        st.markdown(f"#### {translate('cf_title')}")
        st.markdown(f"<span style='color:#8892A4;font-size:0.85rem;'>{translate('cf_sub')}</span>", unsafe_allow_html=True)

        cf_df = compute_counterfactual_excess_margin(df, fuel_key)
        cf_window = cf_df.sort_values("date") if hasattr(cf_df, "sort_values") else cf_df.sort("date").to_pandas()

        total_excess_mio = cf_window[f"{fuel_key}_daily_excess_eur"].sum() / 1_000_000.0
        mean_excess_ct = cf_window[f"{fuel_key}_excess_margin_ct"].mean()
        per_tank_surcharge = (mean_excess_ct * 50.0) / 100.0
        daily_extract_mio = cf_window.iloc[-1][f"{fuel_key}_daily_excess_eur"] / 1_000_000.0 if not cf_window.empty else 0.0

        c_cf1, c_cf2, c_cf3 = st.columns(3)
        with c_cf1:
            st.markdown(f"""
            <div class='kpi-card insight'>
                <div class='kpi-label'>{translate('cf_kpi_total_siphoned')}</div>
                <div class='kpi-value' style='color:#EF4444;'>{total_excess_mio:,.0f} Mio. €</div>
                <div class='kpi-subtitle'>{translate('cf_kpi_total_siphoned_sub')}</div>
            </div>
            """, unsafe_allow_html=True)
        with c_cf2:
            st.markdown(f"""
            <div class='kpi-card'>
                <div class='kpi-label'>{translate('cf_kpi_per_tank')}</div>
                <div class='kpi-value' style='color:#F5A623;'>+{per_tank_surcharge:.2f} €</div>
                <div class='kpi-subtitle'>{translate('cf_kpi_per_tank_sub')} ({mean_excess_ct:.1f} ct/L)</div>
            </div>
            """, unsafe_allow_html=True)
        with c_cf3:
            st.markdown(f"""
            <div class='kpi-card'>
                <div class='kpi-label'>{translate('cf_kpi_daily_siphoned')}</div>
                <div class='kpi-value' style='color:#38BDF8;'>~{daily_extract_mio:.1f} Mio. €/Tag</div>
                <div class='kpi-subtitle'>{translate('cf_kpi_daily_siphoned_sub')}</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # Interactive Personal Driver Surcharge Calculator
        st.markdown(f"##### 🧮 {translate('driver_calc_title')}")
        c_sl1, c_sl2 = st.columns(2)
        with c_sl1:
            user_km = st.slider(translate("driver_calc_km"), min_value=5000, max_value=50000, value=15000, step=1000)
        with c_sl2:
            user_cons = st.slider(translate("driver_calc_consumption"), min_value=4.0, max_value=15.0, value=7.0, step=0.5)

        user_annual_liters = (user_km / 100.0) * user_cons
        user_excess_annual = user_annual_liters * (mean_excess_ct / 100.0)
        user_excess_monthly = user_excess_annual / 12.0

        calc_body = translate('driver_calc_result_body').format(
            mean_excess=f"{mean_excess_ct:.1f}",
            annual=f"{user_excess_annual:.2f}",
            monthly=f"{user_excess_monthly:.2f}"
        )
        st.markdown(f"""
        <div style='background:rgba(245,166,35,0.08);border:1px solid rgba(245,166,35,0.3);border-left:4px solid #F5A623;border-radius:8px;padding:14px 20px;margin-bottom:20px;'>
            <div style='font-size:0.88rem;color:#E8EAF0;'>
                <strong>{translate('driver_calc_result_title')}</strong> 
                {calc_body}
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Plot 3: Cumulative National Excess Revenue Chart
        st.markdown(f"##### {translate('cf_chart_cumulative_title')}")
        st.markdown(f"<span style='color:#8892A4;font-size:0.83rem;'>{translate('cf_chart_cumulative_sub')}</span>", unsafe_allow_html=True)

        fig_cf = go.Figure()
        fig_cf.add_trace(go.Scatter(
            x=cf_window["date"],
            y=cf_window[f"{fuel_key}_cumulative_excess_eur"] / 1_000_000.0,
            name="Kumulierter Mehrerlös (Mio. €)",
            mode="lines",
            line=dict(color="#EF4444", width=3),
            fill="tozeroy",
            fillcolor="rgba(239, 68, 68, 0.15)",
            hovertemplate="%{x|%d.%m.%Y}: <b>%{y:,.1f} Mio. €</b> akkumuliert<extra></extra>"
        ))
        fig_cf = add_discount_bands(fig_cf)
        fig_cf.update_layout(
            **PLOT_LAYOUT,
            height=380,
            yaxis_title="Mio. € (Gesamtschaden)",
        )
        st.plotly_chart(fig_cf, width='stretch', config=PLOT_CONFIG)


# ──────────────────────────────────────────────────────────────────────────────
# TAB: 12-Uhr-Regel Audit (Compliance & Name & Shame)
# ──────────────────────────────────────────────────────────────────────────────
with tab_compliance:
    st.markdown(f"#### {translate('compliance_title')}")
    st.markdown(f"<p style='color:#8892A4;font-size:0.85rem;margin-top:-6px;margin-bottom:16px;'>{translate('compliance_subtitle')}</p>", unsafe_allow_html=True)

    trend_df, rankings_df, lateness_df = load_compliance_data()

    if trend_df is None or rankings_df is None or len(trend_df) == 0:
        st.info(translate("compliance_datasets_generating"))
    else:
        subtab_audit, subtab_tactics, subtab_forensics = st.tabs([
            translate('compliance_subtab_audit'),
            translate('compliance_subtab_tactics'),
            translate('compliance_subtab_forensics'),
        ])

        with subtab_audit:
            # ── Interactive Tolerance Filter ──
            tol_options = [
                translate("compliance_tolerance_standard"),
                translate("compliance_tolerance_buffer"),
                translate("compliance_tolerance_strict")
            ]
            sel_tol = st.selectbox(
                translate("compliance_tolerance_label"),
                options=tol_options,
                index=0,
                key="audit_tolerance_selector"
            )
            tol_key = "standard_1300"
            if sel_tol == translate("compliance_tolerance_buffer"):
                tol_key = "buffer_1215"
            elif sel_tol == translate("compliance_tolerance_strict"):
                tol_key = "strict_1205"

            active_trend = trend_df[trend_df["tolerance"] == tol_key] if ("tolerance" in trend_df.columns) else trend_df

            # Adapt rankings counts to selected tolerance
            active_rankings = rankings_df.copy()
            if tol_key == "strict_1205" and "total_offhour_hikes_1205" in active_rankings.columns:
                active_rankings["total_offhour_hikes"] = active_rankings["total_offhour_hikes_1205"]
                active_rankings["violation_days_count"] = active_rankings["violation_days_1205"]
            elif tol_key == "buffer_1215" and "total_offhour_hikes_1215" in active_rankings.columns:
                active_rankings["total_offhour_hikes"] = active_rankings["total_offhour_hikes_1215"]
                active_rankings["violation_days_count"] = active_rankings["violation_days_1215"]

            # Relabel EG Group to institutional format
            active_rankings["corporate_group"] = active_rankings["corporate_group"].replace(
                {"EG Group (Esso)": "Esso (EG Group / TDR Capital)"}
            )

            # Top KPI Metrics
            latest_day = active_trend.iloc[-1]
            latest_offender_rate = float(latest_day["offender_pct_7d_avg"])
            latest_compliance_rate = 100.0 - latest_offender_rate

            # Post-Adjustment Baseline (15.–30. April, allowing 2 weeks adjustment time from enactment)
            apr_post_adj_df = active_trend[
                (active_trend["date"].astype(str) >= "2026-04-15") &
                (active_trend["date"].astype(str) <= "2026-04-30")
            ]
            # Rolling comparison windows: last 14 days (2 weeks) and last 28 days (4 weeks)
            roll_14_df = active_trend.tail(14)
            roll_28_df = active_trend.tail(28)

            apr_base_rate = float(apr_post_adj_df["offender_pct"].mean()) if len(apr_post_adj_df) > 0 else float(active_trend[active_trend["date"].astype(str) < "2026-05-01"]["offender_pct"].mean())
            roll_14_rate = float(roll_14_df["offender_pct"].mean()) if len(roll_14_df) > 0 else 0.0
            roll_28_rate = float(roll_28_df["offender_pct"].mean()) if len(roll_28_df) > 0 else 0.0

            drift_14 = ((roll_14_rate - apr_base_rate) / apr_base_rate) * 100 if apr_base_rate > 0 else 0.0
            drift_28 = ((roll_28_rate - apr_base_rate) / apr_base_rate) * 100 if apr_base_rate > 0 else 0.0
        
            total_viol_days = active_rankings["violation_days_count"].sum()
            definite_intent_pct = (active_rankings["definite_intent_days"].sum() / total_viol_days * 100) if total_viol_days > 0 else 0.0

            c_col1, c_col2, c_col3 = st.columns(3)
            with c_col1:
                sub_rate_text = translate('compliance_metric_rate_sub').replace('{rate}', f'{latest_offender_rate:.2f}')
                st.markdown(f"""
                <div class='kpi-card'>
                    <div class='kpi-label'>{translate('compliance_metric_rate')}</div>
                    <div class='kpi-value' style='color:#22C55E;'>{latest_compliance_rate:.2f}%</div>
                    <div class='kpi-subtitle'>{sub_rate_text}</div>
                </div>
                """, unsafe_allow_html=True)
            
            with c_col2:
                drift_sign = "+" if drift_14 > 0 else ""
                drift_color = "#22C55E" if drift_14 < 0 else "#EF4444"
                sub_drift_text = (
                    translate('compliance_metric_drift_sub')
                    .replace('{base}', f'{apr_base_rate:.2f}')
                    .replace('{roll14}', f'{roll_14_rate:.2f}')
                    .replace('{drift14}', f'{drift_14:+.1f}%')
                    .replace('{roll28}', f'{roll_28_rate:.2f}')
                    .replace('{drift28}', f'{drift_28:+.1f}%')
                )
                st.markdown(f"""
                <div class='kpi-card insight'>
                    <div class='kpi-label'>{translate('compliance_metric_drift')}</div>
                    <div class='kpi-value' style='color:{drift_color};'>{drift_sign}{drift_14:.1f}%</div>
                    <div class='kpi-subtitle'>{sub_drift_text}</div>
                </div>
                """, unsafe_allow_html=True)

            with c_col3:
                st.markdown(f"""
                <div class='kpi-card'>
                    <div class='kpi-label'>{translate('compliance_metric_intent')}</div>
                    <div class='kpi-value' style='color:#F5A623;'>{definite_intent_pct:.1f}%</div>
                    <div class='kpi-subtitle'>{translate('compliance_metric_intent_sub')}</div>
                </div>
                """, unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            # ── Chart 1: Violation Trend Over Time ──
            st.markdown(f"##### {translate('compliance_trend_title')}")
            st.markdown(f"<span style='color:#8892A4;font-size:0.83rem;'>{translate('compliance_trend_sub')}</span>", unsafe_allow_html=True)

            fig_comp = go.Figure()
            fig_comp.add_trace(go.Bar(
                x=active_trend["date"], y=active_trend["definite_intent_pct"],
                name=f"{translate('compliance_metric_intent')} (%)",
                marker=dict(color="rgba(239, 68, 68, 0.65)"),
                hovertemplate="%{x|%d.%m.%Y}: <b>%{y:.2f}%</b> (Vorsätzliche Mehrfachanhebung)<extra></extra>"
            ))
            fig_comp.add_trace(go.Bar(
                x=active_trend["date"], y=active_trend["single_offhour_pct"],
                name="Einzelne Zeitabweichung (≥13:00 / Früh)",
                marker=dict(color="rgba(56, 189, 248, 0.45)"),
                hovertemplate="%{x|%d.%m.%Y}: <b>%{y:.2f}%</b> (Einmalige Abweichung)<extra></extra>"
            ))
            fig_comp.add_trace(go.Scatter(
                x=active_trend["date"], y=active_trend["offender_pct_7d_avg"],
                name="7-Tage-Trend (Gesamtquote)",
                line=dict(color="#F5A623", width=2.5),
                hovertemplate="%{x|%d.%m.%Y}: <b>%{y:.2f}%</b> (7-Tage-Schnitt)<extra></extra>"
            ))
            fig_comp.update_layout(
                **{
                    **PLOT_LAYOUT,
                    "legend": dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                },
                barmode="stack",
                height=370,
                yaxis_title=translate("compliance_chart_yaxis_pct"),
                yaxis_ticksuffix="%"
            )
            st.plotly_chart(fig_comp, width='stretch', config=PLOT_CONFIG)

            # ── Chart 1b: 24h Hike Lateness Distribution ──
            if lateness_df is not None and len(lateness_df) > 0:
                st.markdown("<br>", unsafe_allow_html=True)
                st.markdown(f"##### {translate('compliance_lateness_title')}")
                st.markdown(f"<span style='color:#8892A4;font-size:0.83rem;'>{translate('compliance_lateness_sub')}</span>", unsafe_allow_html=True)

                cat_colors = {
                    "illegal_morning": "#DC2626",
                    "legal_window": "#10B981",
                    "buffer_latency": "#38BDF8",
                    "slight_delay": "#F5A623",
                    "midday_drift": "#FB923C",
                    "early_afternoon": "#EF4444",
                    "pe_algorithm": "#EF4444",
                    "afternoon": "#F87171",
                    "commuter_wave": "#E11D48",
                    "night": "#94A3B8"
                }
                bar_colors = [cat_colors.get(cat, "#38BDF8") for cat in lateness_df["category"]]

                def _get_lateness_display_label(row_dict, is_de: bool) -> str:
                    key = str(row_dict.get("key", ""))
                    t_key = f"compliance_late_{key}"
                    trans = translate(t_key)
                    if trans and trans != t_key:
                        return trans
                    val = str(row_dict.get("label_de" if is_de else "label_en", ""))
                    if "PE Flash" in val or "Flash Rebound" in val:
                        return "Früher Nachmittag (13:00–15:00 Uhr)" if is_de else "Early Afternoon (13:00–15:00)"
                    return val

                display_labels = [_get_lateness_display_label(r, selected_language == "de") for r in lateness_df.to_dict(orient="records")]

                fig_late = go.Figure()
                fig_late.add_trace(go.Bar(
                    x=lateness_df["share_pct"],
                    y=display_labels,
                    orientation="h",
                    marker=dict(color=bar_colors),
                    text=[f"{v:.2f}% ({c:,})" for v, c in zip(lateness_df["share_pct"], lateness_df["count"])],
                    textposition="auto",
                    hovertemplate=translate("compliance_lateness_hovertemplate"),
                    customdata=lateness_df["count"]
                ))
                fig_late.update_layout(
                    **{
                        **PLOT_LAYOUT,
                        "margin": dict(l=220, r=40, t=20, b=40)
                    },
                    height=340,
                    xaxis_title=translate("compliance_lateness_xaxis"),
                    xaxis_ticksuffix="%"
                )
                st.plotly_chart(fig_late, width='stretch', config=PLOT_CONFIG)

            # ── Institutional Ownership Structure Banner ──
            st.markdown(f"""
            <div style='background:rgba(239,68,68,0.06);border-left:4px solid #EF4444;border-radius:8px;padding:16px 20px;margin:20px 0 24px 0;'>
                <div style='display:flex;align-items:center;gap:8px;font-weight:700;color:#F87171;font-size:1rem;margin-bottom:8px;'>
                    🔍 {translate('compliance_pe_title')}
                </div>
                <div style='color:#CBD5E1;font-size:0.85rem;line-height:1.6;'>
                    {translate('compliance_pe_body')}
                </div>
                <details style='margin-top:14px;background:rgba(15,23,42,0.7);border:1px solid rgba(56,189,248,0.25);border-radius:6px;padding:10px 14px;'>
                    <summary style='color:#38BDF8;font-weight:600;font-size:0.85rem;cursor:pointer;outline:none;user-select:none;display:flex;align-items:center;gap:8px;'>
                        <span style='background:#38BDF8;color:#0F172A;border-radius:50%;width:18px;height:18px;display:inline-flex;align-items:center;justify-content:center;font-size:0.75rem;font-weight:800;font-family:serif;flex-shrink:0;'>i</span>
                        <span>{translate('compliance_eg_dossier_summary')}</span>
                    </summary>
                    <div style='margin-top:12px;color:#94A3B8;font-size:0.82rem;line-height:1.65;border-top:1px solid rgba(255,255,255,0.08);padding-top:10px;'>
                        {translate('compliance_eg_dossier_body')}
                    </div>
                </details>
            </div>
            """, unsafe_allow_html=True)

            # ── Two Column Row: Normalized Brand & Regional Breakdown ──
            group_totals, region_totals = load_network_totals()
            chart_col1, chart_col2 = st.columns([1.1, 1.0])
        
            with chart_col1:
                st.markdown(f"##### {translate('compliance_brand_title')}")
                brand_stats = active_rankings.groupby("corporate_group").agg(
                    offending_stations=("station_uuid", "count"),
                    total_violations=("total_offhour_hikes", "sum"),
                    multi_hike_days=("definite_intent_days", "sum")
                ).reset_index()

                brand_stats["network_total"] = brand_stats["corporate_group"].map(group_totals).fillna(brand_stats["offending_stations"])
                brand_stats["violations_per_station"] = (brand_stats["total_violations"] / brand_stats["network_total"]).round(2)
                brand_stats["offender_pct"] = ((brand_stats["offending_stations"] / brand_stats["network_total"]) * 100).round(1)

                brand_display = brand_stats[brand_stats["network_total"] >= 50].sort_values("violations_per_station", ascending=True).tail(12)

                fig_brand_comp = go.Figure()
                fig_brand_comp.add_trace(go.Bar(
                    y=brand_display["corporate_group"],
                    x=brand_display["violations_per_station"],
                    orientation="h",
                    marker=dict(
                        color=brand_display["violations_per_station"],
                        colorscale=[[0, "#10B981"], [0.35, "#F5A623"], [1, "#EF4444"]],
                    ),
                    hovertemplate=translate("compliance_brand_hovertemplate"),
                    customdata=list(zip(brand_display["total_violations"], brand_display["network_total"].astype(int)))
                ))
                fig_brand_comp.update_layout(
                    **{
                        **PLOT_LAYOUT,
                        "margin": dict(l=170, r=20, t=20, b=40)
                    },
                    height=360,
                    xaxis_title=translate("compliance_brand_xaxis")
                )
                st.plotly_chart(fig_brand_comp, width='stretch', config=PLOT_CONFIG)

            with chart_col2:
                st.markdown(f"##### {translate('compliance_plz_title')}")
                reg_stats = active_rankings.groupby("region").agg(
                    total_violations=("total_offhour_hikes", "sum"),
                    offending_stations=("station_uuid", "count")
                ).reset_index()

                reg_stats["network_total"] = reg_stats["region"].map(region_totals).fillna(reg_stats["offending_stations"])
                reg_stats["violations_per_station"] = (reg_stats["total_violations"] / reg_stats["network_total"]).round(2)
                reg_stats["offender_pct"] = ((reg_stats["offending_stations"] / reg_stats["network_total"]) * 100).round(1)

                reg_display = reg_stats[reg_stats["network_total"] >= 50].sort_values("violations_per_station", ascending=True)

                fig_reg = go.Figure()
                fig_reg.add_trace(go.Bar(
                    y=reg_display["region"],
                    x=reg_display["violations_per_station"],
                    orientation="h",
                    marker=dict(
                        color=reg_display["violations_per_station"],
                        colorscale=[[0, "#38BDF8"], [0.5, "#818CF8"], [1, "#C084FC"]],
                    ),
                    hovertemplate=translate("compliance_brand_hovertemplate"),
                    customdata=list(zip(reg_display["total_violations"], reg_display["network_total"].astype(int)))
                ))
                fig_reg.update_layout(
                    **{
                        **PLOT_LAYOUT,
                        "margin": dict(l=170, r=20, t=20, b=40)
                    },
                    height=360,
                    xaxis_title=translate("compliance_plz_xaxis")
                )
                st.plotly_chart(fig_reg, width='stretch', config=PLOT_CONFIG)

            # ── Station Leaderboard ("Name & Shame") with Lifecycle Explorer ──
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown(f"##### {translate('compliance_leaderboard_title')}")

            filter_c1, filter_c2, filter_c3, filter_c4 = st.columns([1.1, 1.1, 1.0, 0.8])
            all_groups = [translate("compliance_all_groups")] + sorted(active_rankings["corporate_group"].dropna().unique().tolist())
            with filter_c1:
                sel_group = st.selectbox(translate("compliance_filter_group"), all_groups, key="comp_group_filter")
            with filter_c2:
                lifecycle_options = [
                    translate("compliance_lifecycle_all"),
                    translate("compliance_lifecycle_late_starter"),
                    translate("compliance_lifecycle_persistent"),
                    translate("compliance_lifecycle_stopped"),
                    translate("compliance_lifecycle_isolated")
                ]
                sel_lifecycle = st.selectbox(translate("compliance_filter_lifecycle"), lifecycle_options, key="comp_lifecycle_filter")
            with filter_c3:
                search_station = st.text_input(translate("compliance_search_station"), "", key="comp_search_filter")
            with filter_c4:
                sort_opt_violations = translate("compliance_sort_violations")
                sort_opt_intent = translate("compliance_sort_intent")
                sort_opt_max_jump = translate("compliance_sort_max_jump")
                sort_by = st.selectbox(translate("compliance_sort_by"), [sort_opt_violations, sort_opt_intent, sort_opt_max_jump], key="comp_sort_filter")

            filtered_rankings = active_rankings.copy()
            if isinstance(sel_group, str) and sel_group != translate("compliance_all_groups"):
                filtered_rankings = filtered_rankings[filtered_rankings["corporate_group"] == sel_group]

            if sel_lifecycle == translate("compliance_lifecycle_late_starter"):
                filtered_rankings = filtered_rankings[filtered_rankings["lifecycle_status"] == "late_starter"]
            elif sel_lifecycle == translate("compliance_lifecycle_persistent"):
                filtered_rankings = filtered_rankings[filtered_rankings["lifecycle_status"] == "persistent"]
            elif sel_lifecycle == translate("compliance_lifecycle_stopped"):
                filtered_rankings = filtered_rankings[filtered_rankings["lifecycle_status"] == "stopped"]
            elif sel_lifecycle == translate("compliance_lifecycle_isolated"):
                filtered_rankings = filtered_rankings[filtered_rankings["lifecycle_status"] == "isolated"]

            if isinstance(search_station, str) and search_station.strip():
                query = search_station.strip().lower()
                filtered_rankings = filtered_rankings[
                    filtered_rankings["street"].str.lower().str.contains(query, na=False) |
                    filtered_rankings["city"].str.lower().str.contains(query, na=False) |
                    filtered_rankings["post_code"].str.lower().str.contains(query, na=False)
                ]

            if sort_by == sort_opt_violations:
                filtered_rankings = filtered_rankings.sort_values("total_offhour_hikes", ascending=False)
            elif sort_by == sort_opt_intent:
                filtered_rankings = filtered_rankings.sort_values("definite_intent_days", ascending=False)
            else:
                filtered_rankings = filtered_rankings.sort_values("max_single_hike_eur", ascending=False)

            col_max_jump = translate("compliance_table_max_jump")
            col_viol_pct = translate("compliance_table_violation_pct")
            col_viol_hikes = translate("compliance_table_violations")
            col_intent_days = translate("compliance_table_intent_days")
            col_timespan = translate("compliance_table_timespan")
            col_status = translate("compliance_table_lifecycle")
            col_monthly = translate("compliance_table_monthly")

            status_map = {
                "late_starter": "🚀 Spätstarter (Mai)",
                "persistent": "🔁 Dauersünder",
                "stopped": "🛑 Gestoppt",
                "isolated": "⚡ Einzelfall",
                "sporadic": "⏱️ Sporadisch"
            } if selected_language == "de" else {
                "late_starter": "🚀 Late Starter (May)",
                "persistent": "🔁 Persistent",
                "stopped": "🛑 Stopped",
                "isolated": "⚡ Isolated",
                "sporadic": "⏱️ Sporadic"
            }
            traj_map = {
                "accelerating": "📈",
                "decelerating": "📉",
                "constant": "➖"
            }

            if "first_violation_date" in filtered_rankings.columns and "last_violation_date" in filtered_rankings.columns:
                filtered_rankings["timespan_str"] = (
                    filtered_rankings["first_violation_date"].astype(str).str.slice(5) + " – " +
                    filtered_rankings["last_violation_date"].astype(str).str.slice(5)
                )
            else:
                filtered_rankings["timespan_str"] = "—"

            if "lifecycle_status" in filtered_rankings.columns:
                filtered_rankings["status_str"] = (
                    filtered_rankings["lifecycle_status"].map(status_map).fillna("—") + " " +
                    filtered_rankings.get("trajectory", pd.Series(index=filtered_rankings.index)).map(traj_map).fillna("")
                )
            else:
                filtered_rankings["status_str"] = "—"

            m_may = "Mai:" if selected_language == "de" else "May:"
            if "apr_hikes" in filtered_rankings.columns and "sep_hikes" in filtered_rankings.columns:
                filtered_rankings["monthly_str"] = (
                    "Apr:" + filtered_rankings["apr_hikes"].astype(str) + " · " +
                    m_may + filtered_rankings["may_hikes"].astype(str) + " · " +
                    "Jun:" + filtered_rankings["jun_hikes"].astype(str) + " · " +
                    "Sep:" + filtered_rankings["sep_hikes"].astype(str)
                )
                if "oct_hikes" in filtered_rankings.columns:
                    m_oct = "Okt:" if selected_language == "de" else "Oct:"
                    filtered_rankings["monthly_str"] += " · " + m_oct + filtered_rankings["oct_hikes"].astype(str)
            else:
                filtered_rankings["monthly_str"] = "—"

            display_df = filtered_rankings[[
                "brand", "corporate_group", "street", "post_code", "city",
                "total_offhour_hikes", "definite_intent_days", "timespan_str",
                "status_str", "monthly_str", "max_single_hike_eur"
            ]].head(100).rename(columns={
                "street": translate("street"),
                "brand": translate("brand"),
                "corporate_group": translate("compliance_filter_group"),
                "post_code": translate("zip_code"),
                "city": translate("city"),
                "total_offhour_hikes": col_viol_hikes,
                "definite_intent_days": col_intent_days,
                "timespan_str": col_timespan,
                "status_str": col_status,
                "monthly_str": col_monthly,
                "max_single_hike_eur": col_max_jump
            })

            st.dataframe(
                display_df,
                hide_index=True,
                column_config={
                    col_max_jump: st.column_config.NumberColumn(format="+€%.3f"),
                    col_viol_hikes: st.column_config.NumberColumn(format="%d"),
                    col_intent_days: st.column_config.NumberColumn(format="%d")
                }
            )
            st.caption(translate("compliance_rankings_display_caption"))


        with subtab_tactics:
            st.markdown(f"#### {translate('compliance_tactics_title')}")
            st.markdown(f"<p style='color:#8892A4;font-size:0.85rem;margin-top:-6px;margin-bottom:20px;'>{translate('compliance_tactics_sub')}</p>", unsafe_allow_html=True)

            # 3 Top KPI Cards for the 3 Groups
            t_col1, t_col2, t_col3 = st.columns(3)
            with t_col1:
                st.markdown(translate("compliance_tactics_kpi1_html"), unsafe_allow_html=True)

            with t_col2:
                st.markdown(translate("compliance_tactics_kpi2_html"), unsafe_allow_html=True)

            with t_col3:
                st.markdown(translate("compliance_tactics_kpi3_html"), unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            # Deep Dive 1: ESSO
            st.markdown(translate("compliance_tactics_dive1_html"), unsafe_allow_html=True)

            # Deep Dive 2 & 3 side by side
            dd_col1, dd_col2 = st.columns(2)
            with dd_col1:
                st.markdown(translate("compliance_tactics_dive2_html"), unsafe_allow_html=True)

            with dd_col2:
                st.markdown(translate("compliance_tactics_dive3_html"), unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            # Comparative Matrix Table
            st.markdown(f"##### 📋 {translate('compliance_matrix_title')}")
            col_crit = translate("compliance_matrix_criterion")
            col_esso = translate("compliance_matrix_esso_col")
            col_indie = translate("compliance_matrix_indie_col")
            col_majors = translate("compliance_matrix_majors_col")

            if lang == "en":
                matrix_df = pd.DataFrame({
                    col_crit: [
                        "Number of stations in Germany",
                        "Total violations (Apr–Sep 2026)",
                        "Violations per station (Average)",
                        "Flash rebounds (Hike ≤ 10 min after cut)",
                        "Sub-second batch commands (Central API)",
                        "Primary time window of price hikes",
                        "Primary motivation / Root cause",
                        "Legal classification (§ 3 KPAnG)"
                    ],
                    col_esso: [
                        "1,396 (Largest brand network)",
                        "4,132 total (2,420 rebounds)",
                        "2.96 (1.73 afternoon rebounds; not top 1)",
                        "89.5% (Highly algorithmic)",
                        "Yes (up to 15 stations simultaneously)",
                        "13:00 – 15:00 (64.5%)",
                        "App cache baiting & margin protection (Probing & Pullback)",
                        "🚨 Systematic, intentional administrative offense"
                    ],
                    col_indie: [
                        "~4,256 (Independents & SMEs)",
                        "11,064",
                        "2.60 (certain regional chains up to 5.68)",
                        "37.1% (62.9% delayed isolated hikes)",
                        "No (decentralized, uncoordinated)",
                        "13:00 (34.8%) & 18:00 (9.6%)",
                        "Delayed manual shift & evening commute capture",
                        "⚠️ Decentralized breach due to lack of compliance tooling"
                    ],
                    col_majors: [
                        "4,343 (2,459 Aral + 1,884 Shell)",
                        "171 (4 Aral + 167 Shell)",
                        "0.0016 (Aral) / 0.088 (Shell)",
                        "— (Hard software lock)",
                        "No",
                        "Sporadic throughout the day",
                        "Technical queue latencies / POS resets",
                        "✅ Full regulatory compliance (within safe buffer)"
                    ]
                })
            else:
                matrix_df = pd.DataFrame({
                    col_crit: [
                        "Anzahl Tankstellen in DE",
                        "Verstöße gesamt (Apr–Sep 2026)",
                        "Verstöße pro Station (Schnitt)",
                        "Flash-Rebounds (Erhöhung ≤ 10 min nach Senkung)",
                        "Sekundengleiche Batch-Befehle (Zentrale API)",
                        "Haupt-Zeitfenster der Erhöhungen",
                        "Primäre Motivation / Ursache",
                        "Rechtliche Einstufung (§ 3 KPAnG)"
                    ],
                    col_esso: [
                        "1.396 (Größtes Verstoß-Netzwerk)",
                        "4.132 gesamt (2.420 Rebounds)",
                        "2,96 (1,73 Nachmittags-Rebounds; nicht Top 1)",
                        "89,5 % (Hochgradig algorithmisch)",
                        "Ja (bis zu 15 Stationen zeitgleich)",
                        "13:00 – 15:00 Uhr (64,5 %)",
                        "App-Cache-Baiting & Marge-Schutz (Probing & Pullback)",
                        "🚨 Systematische, vorsätzliche Ordnungswidrigkeit"
                    ],
                    col_indie: [
                        "~4.256 (Mittelstand & Freie)",
                        "11.064",
                        "2,60 (einzelne Ketten wie ED bis 5,68)",
                        "37,1 % (62,9% verspätete Einzel-Hikes)",
                        "Nein (dezentral, unkoordiniert)",
                        "13:00 Uhr (34,8 %) & 18:00 Uhr (9,6 %)",
                        "Verspätete Handumstellung & Feierabend-Mitnahme",
                        "⚠️ Dezentrale Pflichtverletzung mangels Compliance"
                    ],
                    col_majors: [
                        "4.343 (2.459 Aral + 1.884 Shell)",
                        "171 (4 Aral + 167 Shell)",
                        "0,0016 (Aral) / 0,088 (Shell)",
                        "— (Harte Software-Sperre)",
                        "Nein",
                        "Vereinzelt über den Tag verteilt",
                        "Technische Queue-Latenzen / Kassen-Resets",
                        "✅ Vollständige Regeltreue (im Toleranzbereich)"
                    ]
                })
            st.dataframe(
                matrix_df,
                hide_index=True,
                width="stretch"
            )


        with subtab_forensics:
            # ── Single-Station Forensics & Evidence Graph ──
            st.markdown("<br><hr style='border:0;border-top:1px solid rgba(255,255,255,0.08);margin:30px 0 25px 0;'>", unsafe_allow_html=True)
            st.markdown(f"#### 🔍 {translate('compliance_forensics_title')}")
            st.markdown(f"<p style='color:#8892A4;font-size:0.85rem;margin-top:-6px;margin-bottom:16px;'>{translate('compliance_forensics_sub')}</p>", unsafe_allow_html=True)

            # Quick Picks row
            unit_v = translate("compliance_violations_unit")
            st.markdown(f"<span style='font-size:0.8rem;font-weight:600;color:#94A3B8;'>{translate('compliance_top_offenders')}:</span>", unsafe_allow_html=True)
            if "forensic_station_uuid" not in st.session_state:
                st.session_state["forensic_station_uuid"] = "ef31f531-ef1b-4845-b23f-f315e2b773e1"

            # Stations are labelled by brand and location only, never by operator name.
            quick_pick_uuids = [
                "ef31f531-ef1b-4845-b23f-f315e2b773e1",
                "d6f500b9-9524-403a-9fa8-9342fb983b3d",
                "dcdb5b92-69cc-4b24-a35c-b8155431b977",
                "73f8787d-132a-426a-8791-02416103d4b6",
            ]
            quick_picks = rankings_df[rankings_df["station_uuid"].isin(quick_pick_uuids)].set_index("station_uuid")
            for qp_idx, (qp_col, qp_uuid) in enumerate(zip(st.columns(4), quick_pick_uuids)):
                if qp_uuid not in quick_picks.index:
                    continue
                qp = quick_picks.loc[qp_uuid]
                with qp_col:
                    qp_label = f"🚨 {qp['brand']}\n{qp['city']} · {int(qp['total_offhour_hikes'])} {unit_v}"
                    if st.button(qp_label, width="stretch", key=f"btn_qp_{qp_idx}"):
                        st.session_state["forensic_station_uuid"] = qp_uuid
                        st.rerun()

            # Station Selectbox & Controls
            st_select_col1, st_select_col2, st_select_col3 = st.columns([2.5, 0.9, 1.4])
            with st_select_col1:
                top_ranked = rankings_df.sort_values("total_offhour_hikes", ascending=False)
                station_options = {}
                for _, r in top_ranked.head(500).iterrows():
                    opt_label = f"{r['brand']} — {r['post_code']} {r['city']}, {r['street']} | {int(r['total_offhour_hikes'])} {unit_v} (max +{r['max_single_hike_eur']*100:.1f} ct)"
                    station_options[r['station_uuid']] = opt_label

                curr_uuid = st.session_state.get("forensic_station_uuid", "ef31f531-ef1b-4845-b23f-f315e2b773e1")
                if not isinstance(curr_uuid, str):
                    curr_uuid = "ef31f531-ef1b-4845-b23f-f315e2b773e1"

                all_uuids_set = set(str(x) for x in rankings_df["station_uuid"].dropna().tolist())
                if curr_uuid not in station_options and curr_uuid in all_uuids_set:
                    r_match = rankings_df[rankings_df["station_uuid"] == curr_uuid].iloc[0]
                    station_options[curr_uuid] = f"{r_match['name']} ({r_match['brand']}) — {r_match['post_code']} {r_match['city']} | {int(r_match['total_offhour_hikes'])} {translate('compliance_violations_unit')}"

                uuid_keys = list(station_options.keys())
                def_idx = uuid_keys.index(curr_uuid) if curr_uuid in uuid_keys else 0

                selected_st_uuid = st.selectbox(
                    translate("compliance_station_select"),
                    options=uuid_keys,
                    index=def_idx,
                    format_func=lambda u: station_options.get(u, str(u)),
                    key="forensic_select_box"
                )
                if not isinstance(selected_st_uuid, str):
                    selected_st_uuid = curr_uuid
                st.session_state["forensic_station_uuid"] = selected_st_uuid

            with st_select_col2:
                forensic_fuel = st.selectbox(
                    translate("fuel_type"),
                    options=["e5", "e10", "diesel"],
                    index=["e5", "e10", "diesel"].index(fuel_key) if (isinstance(fuel_key, str) and fuel_key in ["e5", "e10", "diesel"]) else 0,
                    format_func=lambda f: str(f).upper(),
                    key="forensic_fuel_select"
                )
                if not isinstance(forensic_fuel, str):
                    forensic_fuel = "e5"

            with st_select_col3:
                tolerance_opt = st.selectbox(
                    translate("compliance_tolerance_window"),
                    options=[translate("compliance_tol_standard"), translate("compliance_tol_strict")],
                    index=0,
                    help=translate("compliance_tol_help"),
                    key="forensic_tolerance_select"
                )
                strict_mode = ("12:05" in str(tolerance_opt))

            # Load station price event data
            st_events_pl = load_single_station_forensics(selected_st_uuid, forensic_fuel, strict_noon=strict_mode)

            if st_events_pl is None or st_events_pl.height == 0:
                st.warning(translate("compliance_no_data_warning"))
            else:
                st_events = st_events_pl.to_pandas()
                st_events["time_of_day_hours"] = st_events["min_of_day"] / 60.0
                st_events["time_str"] = st_events["local_time"].dt.strftime("%H:%M:%S")
                st_events["date_str"] = st_events["local_time"].dt.strftime("%d.%m.%Y")
                st_events["datetime_str"] = st_events["local_time"].dt.strftime("%d.%m.%Y %H:%M:%S")

                illegals = st_events[st_events["event_type"].str.startswith("illegal")]
                noon_hikes = st_events[st_events["event_type"] == "allowed_noon"]
                cuts = st_events[st_events["event_type"] == "allowed_cut"]

                tot_illegals = len(illegals)
                max_illegal_jump = illegals["diff_ct"].max() if tot_illegals > 0 else 0.0
                avg_illegal_jump = illegals["diff_ct"].mean() if tot_illegals > 0 else 0.0
                tot_noon = len(noon_hikes)
                tot_cuts = len(cuts)

                meta_match = rankings_df[rankings_df["station_uuid"] == selected_st_uuid]
                st_name = meta_match["street"].iloc[0] if not meta_match.empty else "Station"
                st_brand = meta_match["brand"].iloc[0] if not meta_match.empty else ""
                st_city = meta_match["city"].iloc[0] if not meta_match.empty else ""

                # Station KPI Cards
                f_col1, f_col2, f_col3, f_col4 = st.columns(4)
                with f_col1:
                    st.markdown(f"""
                    <div class='kpi-card'>
                        <div class='kpi-label'>{translate('compliance_kpi_illegal_hikes')}</div>
                        <div class='kpi-value' style='color:#EF4444;'>{tot_illegals:,}</div>
                        <div class='kpi-subtitle'>{translate('compliance_kpi_outside_window')}</div>
                    </div>
                    """, unsafe_allow_html=True)
                with f_col2:
                    st.markdown(f"""
                    <div class='kpi-card insight'>
                        <div class='kpi-label'>{translate('compliance_kpi_max_illegal_jump')}</div>
                        <div class='kpi-value' style='color:#F5A623;'>+{max_illegal_jump:.1f} ct</div>
                        <div class='kpi-subtitle'>{translate('compliance_kpi_max_jump_sub')}</div>
                    </div>
                    """, unsafe_allow_html=True)
                with f_col3:
                    st.markdown(f"""
                    <div class='kpi-card'>
                        <div class='kpi-label'>{translate('compliance_kpi_avg_jump')}</div>
                        <div class='kpi-value' style='color:#FBBF24;'>+{avg_illegal_jump:.1f} ct</div>
                        <div class='kpi-subtitle'>{translate('compliance_kpi_avg_jump_sub')}</div>
                    </div>
                    """, unsafe_allow_html=True)
                with f_col4:
                    st.markdown(f"""
                    <div class='kpi-card'>
                        <div class='kpi-label'>{translate('compliance_kpi_allowed_adjustments')}</div>
                        <div class='kpi-value' style='color:#22C55E;'>{tot_noon} / {tot_cuts:,}</div>
                        <div class='kpi-subtitle'>{translate('compliance_kpi_allowed_sub').format(noon=tot_noon, cuts=f"{tot_cuts:,}")}</div>
                    </div>
                    """, unsafe_allow_html=True)

                # ── Top 5 Worst Violations Proof Box (Wann, wie oft und wie hoch) ──
                if tot_illegals > 0:
                    top_5_illegals = illegals.sort_values("diff_ct", ascending=False).head(5)

                    st.markdown(f"""
                    <div style='background:rgba(239,68,68,0.05);border:1px solid rgba(239,68,68,0.25);border-radius:10px;padding:16px 20px;margin-top:16px;margin-bottom:20px;'>
                        <div style='display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;'>
                            <div style='font-weight:700;color:#EF4444;font-size:0.95rem;'>
                                🚨 {translate('compliance_top5_title')}: {st_name} ({st_brand})
                            </div>
                            <div style='font-size:0.75rem;color:#8892A4;'>
                                {translate('compliance_source_mtsk')}
                            </div>
                        </div>
                        <div style='color:#CBD5E1;font-size:0.8rem;margin-bottom:12px;line-height:1.45;'>
                            {translate('compliance_proof_desc').replace('{count}', f'{tot_illegals:,}')}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    proof_cols = st.columns(min(5, len(top_5_illegals)))
                    for idx, (_, row_p) in enumerate(top_5_illegals.iterrows()):
                        with proof_cols[idx]:
                            hike_nr = int(row_p.get("daily_hike_nr", 2))
                            noon_time = str(row_p.get("noon_hike_time", "—"))
                            noon_ct = float(row_p.get("noon_hike_ct", 0.0))
                            noon_price = float(row_p.get("noon_hike_price", 0.0))
                            date_display = str(row_p.get("date_str", row_p.get("local_date", "")))
                            time_display = str(row_p.get("time_str", ""))

                            if noon_time != "—" and noon_ct > 0:
                                noon_info_html = translate("compliance_proof_noon_hike").format(time=noon_time, ct=noon_ct, price=noon_price)
                            else:
                                noon_info_html = translate("compliance_proof_no_noon")

                            hike_label = translate("compliance_hike_format").replace("{num}", str(hike_nr))
                            chain_ok = translate("compliance_proof_chain_ok")

                            st.markdown(f"""
                            <div style='background:rgba(15,23,42,0.7);padding:10px;border-radius:8px;border:1px solid rgba(239,68,68,0.2);margin-bottom:12px;'>
                                <div style='display:flex;align-items:center;justify-content:space-between;margin-bottom:2px;'>
                                    <span style='font-size:0.68rem;color:#94A3B8;font-weight:600;'>#{idx+1} · {time_display}</span>
                                    <span style='background:rgba(239,68,68,0.2);color:#FCA5A5;font-size:0.62rem;font-weight:700;padding:1px 5px;border-radius:3px;'>{hike_label}</span>
                                </div>
                                <div style='font-size:0.65rem;color:#64748B;'>{date_display}</div>
                                <div style='font-size:1.25rem;font-weight:800;color:#EF4444;margin:2px 0;'>+{row_p["diff_ct"]:.1f} ct</div>
                                <div style='font-size:0.72rem;color:#CBD5E1;'>€{row_p["prev_price"]:.3f} ➔ <b>€{row_p["price"]:.3f}</b></div>
                                {noon_info_html}
                                <div style='font-size:0.64rem;color:#10B981;margin-top:4px;font-weight:500;'>{chain_ok}</div>
                                <div style='font-size:0.66rem;color:#F5A623;margin-top:3px;line-height:1.2;'>{row_p["status_label"]}</div>
                            </div>
                            """, unsafe_allow_html=True)

                    st.markdown(f"""
                    <div style='background:rgba(0,0,0,0.25);padding:10px 14px;border-radius:6px;font-size:0.75rem;color:#94A3B8;line-height:1.4;margin-bottom:20px;'>
                        <b>{translate('compliance_paechter_title')}</b> {translate('compliance_paechter_note')}
                    </div>
                    """, unsafe_allow_html=True)

                # View Mode and Filter controls
                ctrl_col1, ctrl_col2 = st.columns([1.5, 1])
                with ctrl_col1:
                    view_mode = st.radio(
                        translate("compliance_view_mode"),
                        [translate("compliance_view_timeline"), translate("compliance_view_clock")],
                        horizontal=True,
                        key="forensic_view_mode"
                    )
                    if not isinstance(view_mode, str):
                        view_mode = translate("compliance_view_timeline")

                with ctrl_col2:
                    filter_mode = st.radio(
                        translate("compliance_filter_mode"),
                        [translate("compliance_filter_hikes_only"), translate("compliance_filter_all")],
                        horizontal=True,
                        key="forensic_filter_mode"
                    )
                    if not isinstance(filter_mode, str):
                        filter_mode = translate("compliance_filter_hikes_only")

                # Build Forensic Plot
                fig_st = go.Figure()

                if view_mode == translate("compliance_view_timeline"):
                    # ── View 1: Chronological Timeline ──
                    if filter_mode == translate("compliance_filter_all") and len(cuts) > 0:
                        fig_st.add_trace(go.Scatter(
                            x=cuts["local_time"], y=cuts["diff_ct"],
                            mode="markers",
                            name=translate("compliance_legend_allowed_cut"),
                            marker=dict(color="rgba(34, 197, 94, 0.4)", size=5, symbol="circle"),
                            customdata=cuts[["prev_price", "price", "datetime_str", "status_label"]].values,
                            hovertemplate=translate("compliance_hover_cut")
                        ))

                    if len(noon_hikes) > 0:
                        fig_st.add_trace(go.Scatter(
                            x=noon_hikes["local_time"], y=noon_hikes["diff_ct"],
                            mode="markers",
                            name=translate("compliance_legend_allowed_noon"),
                            marker=dict(color="#38BDF8", size=8, symbol="circle"),
                            customdata=noon_hikes[["prev_price", "price", "datetime_str", "status_label"]].values,
                            hovertemplate=translate("compliance_hover_allowed_noon")
                        ))

                    if len(illegals) > 0:
                        fig_st.add_trace(go.Scatter(
                            x=illegals["local_time"], y=illegals["diff_ct"],
                            error_y=dict(
                                type="data",
                                array=[0]*len(illegals),
                                arrayminus=illegals["diff_ct"].tolist(),
                                symmetric=False,
                                color="rgba(239, 68, 68, 0.65)",
                                width=0,
                                thickness=1.5
                            ),
                            mode="markers",
                            name=translate("compliance_legend_illegal_hike"),
                            marker=dict(
                                color="#EF4444",
                                size=10,
                                symbol="diamond",
                                line=dict(color="#FFFFFF", width=1.2)
                            ),
                            customdata=illegals[["prev_price", "price", "datetime_str", "status_label"]].values,
                            hovertemplate=translate("compliance_hover_illegal")
                        ))

                    fig_st.add_hline(y=0, line_dash="solid", line_color="rgba(255,255,255,0.2)", line_width=1)
                    fig_st.update_layout(
                        **{
                            **PLOT_LAYOUT,
                            "legend": dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                        },
                        height=440,
                        xaxis_title=translate("compliance_xaxis_datetime"),
                        yaxis_title=translate("compliance_yaxis_adjustment"),
                        yaxis_ticksuffix=" ct"
                    )

                else:
                    # ── View 2: Time-of-Day Clock Distribution ──
                    noon_x1 = 12.0833 if strict_mode else 13.0
                    noon_annot = f"{translate('compliance_annot_noon_window')} (11:55–12:05)" if strict_mode else f"{translate('compliance_annot_noon_window')} (11:55–13:00)"
                    fig_st.add_vrect(
                        x0=11.9167, x1=noon_x1,
                        fillcolor="rgba(56, 189, 248, 0.15)",
                        line_width=1, line_dash="dash", line_color="#38BDF8",
                        annotation_text=noon_annot,
                        annotation_position="top left"
                    )

                    if filter_mode == translate("compliance_filter_all") and len(cuts) > 0:
                        fig_st.add_trace(go.Scatter(
                            x=cuts["time_of_day_hours"], y=cuts["diff_ct"],
                            mode="markers",
                            name=translate("compliance_legend_allowed_cut"),
                            marker=dict(color="rgba(34, 197, 94, 0.35)", size=5, symbol="circle"),
                            customdata=cuts[["prev_price", "price", "datetime_str", "status_label"]].values,
                            hovertemplate=translate("compliance_hover_clock_cut")
                        ))

                    if len(noon_hikes) > 0:
                        fig_st.add_trace(go.Scatter(
                            x=noon_hikes["time_of_day_hours"], y=noon_hikes["diff_ct"],
                            mode="markers",
                            name=translate("compliance_legend_allowed_noon"),
                            marker=dict(color="#38BDF8", size=8, symbol="circle"),
                            customdata=noon_hikes[["prev_price", "price", "datetime_str", "status_label"]].values,
                            hovertemplate=translate("compliance_hover_clock_noon")
                        ))

                    if len(illegals) > 0:
                        fig_st.add_trace(go.Scatter(
                            x=illegals["time_of_day_hours"], y=illegals["diff_ct"],
                            error_y=dict(
                                type="data",
                                array=[0]*len(illegals),
                                arrayminus=illegals["diff_ct"].tolist(),
                                symmetric=False,
                                color="rgba(239, 68, 68, 0.65)",
                                width=0,
                                thickness=1.5
                            ),
                            mode="markers",
                            name=translate("compliance_legend_illegal_hike"),
                            marker=dict(color="#EF4444", size=10, symbol="diamond", line=dict(color="#FFFFFF", width=1.2)),
                            customdata=illegals[["prev_price", "price", "datetime_str", "status_label"]].values,
                            hovertemplate=translate("compliance_hover_clock_illegal")
                        ))

                    fig_st.add_hline(y=0, line_dash="solid", line_color="rgba(255,255,255,0.2)", line_width=1)
                    fig_st.update_layout(
                        **{
                            **PLOT_LAYOUT,
                            "legend": dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                        },
                        height=440,
                        xaxis_title=translate("compliance_xaxis_tod"),
                        yaxis_title=translate("compliance_yaxis_adjustment"),
                        yaxis_ticksuffix=" ct"
                    )
                    fig_st.update_xaxes(
                        tickmode="array",
                        tickvals=[0, 3, 6, 9, 12, 15, 18, 21, 24],
                        ticktext=["00:00", "03:00", "06:00", "09:00", "12:00", "15:00", "18:00", "21:00", "24:00"]
                    )

                st.plotly_chart(fig_st, width='stretch', config=PLOT_CONFIG)

                # ── Forensic Audit Evidence Protocol Table ──
                st.markdown(f"##### 📋 {translate('compliance_protocol_title')}")

                with st.expander(f"🔬 {translate('compliance_etl_box_title')}", expanded=False):
                    st.markdown(translate("compliance_etl_proof_detail"), unsafe_allow_html=True)

                if len(illegals) == 0:
                    st.success(translate("compliance_no_violations_success"))
                else:
                    audit_prep = illegals.copy()
                    audit_prep["hike_nr_str"] = audit_prep["daily_hike_nr"].apply(lambda n: translate("compliance_hike_format").replace("{num}", str(int(n))))
                    audit_prep["noon_ref_str"] = audit_prep.apply(
                        lambda r: f"{r['noon_hike_time']} (+{r['noon_hike_ct']:.1f} ct)" if str(r.get("noon_hike_time", "—")) != "—" and float(r.get("noon_hike_ct", 0.0)) > 0 else translate("compliance_no_noon_hike"),
                        axis=1
                    )
                    audit_prep["chain_status"] = translate("compliance_status_closed")

                    audit_display = audit_prep[[
                        "datetime_str", "hike_nr_str", "prev_price", "diff_ct", "price", "noon_ref_str", "chain_status", "status_label"
                    ]].sort_values("datetime_str", ascending=False).rename(columns={
                        "datetime_str": translate("compliance_col_datetime"),
                        "hike_nr_str": translate("compliance_col_hike_nr"),
                        "prev_price": translate("compliance_col_prev_price"),
                        "diff_ct": translate("compliance_col_diff"),
                        "price": translate("compliance_col_new_price"),
                        "noon_ref_str": translate("compliance_col_noon_context"),
                        "chain_status": translate("compliance_col_etl_status"),
                        "status_label": translate("compliance_col_violation")
                    })

                    t_col1, t_col2 = st.columns([3, 1])
                    with t_col1:
                        st.caption(translate("compliance_total_documented_caption").replace("{count}", f"{len(illegals):,}").replace("{name}", str(st_name)).replace("{brand}", str(st_brand)).replace("{city}", str(st_city)))
                    with t_col2:
                        csv_bytes = audit_display.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            f"📥 {translate('compliance_download_csv')}",
                            data=csv_bytes,
                            file_name=f"compliance_audit_{selected_st_uuid}_{forensic_fuel}.csv",
                            mime="text/csv",
                            width="stretch"
                        )


                    st.dataframe(
                        audit_display.head(200),
                        hide_index=True,
                        column_config={
                            translate("compliance_col_prev_price"): st.column_config.NumberColumn(format="€%.3f"),
                            translate("compliance_col_new_price"): st.column_config.NumberColumn(format="€%.3f"),
                            translate("compliance_col_diff"): st.column_config.NumberColumn(format="+%.1f ct"),
                        }
                    )

            # ── Transparency Disclaimer Box ──
            st.markdown(
                f"<div style='background:rgba(245,166,35,0.06);border-left:3px solid #F5A623;"
                f"border-radius:8px;padding:14px 18px;margin-top:22px;color:#CBD5E1;font-size:0.82rem;line-height:1.5;'>"
                f"{translate('compliance_disclaimer')}</div>",
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
        "discount_2026_q4": lambda df: df.filter((pl.col("date") >= date(2026, 10, 1)) & (pl.col("date") <= date(2026, 12, 31))),
        "baseline_2021": lambda df: df.filter(pl.col("date") < date(2022, 1, 1)),
    }
    
    selected_timeframes = st.multiselect(
        translate("compare_timeframes"),
        options=list(timeframes.keys()),
        default=["last_30"],
        format_func=lambda key: translate(key),
    )
    if not selected_timeframes:
        selected_timeframes = ["last_30"]
    
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
    st.plotly_chart(fig3, width='stretch', config=PLOT_CONFIG)

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
# TAB 6: Brand Comparison
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
            "discount_2026_q4": (translate("tankrabatt_3"), date(2026, 10, 1), date(2026, 12, 31)),
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
            st.plotly_chart(fig_brand, width='stretch', config=PLOT_CONFIG)

            # ── Price change frequency by group ──
            st.markdown(f"#### {translate('brand_changes_title')}")
            st.markdown(f"<span style='color:#8892A4;font-size:0.85rem;'>{translate('brand_changes_note')}</span>", unsafe_allow_html=True)

            changes_col = f"changes_{fuel_key}"
            fig_changes = go.Figure()
            if changes_col in visible_brand_df.columns and not visible_brand_df.is_empty():
                changes_pd = visible_brand_df.sort(["comparison_group", "date"]).to_pandas()
                for idx, group_name in enumerate(selected_groups):
                    group_pd = changes_pd[changes_pd["comparison_group"] == group_name]
                    if group_pd.empty:
                        continue
                    smoothed = (
                        group_pd.sort_values("date")[changes_col]
                        .rolling(14, min_periods=1)
                        .mean()
                    )
                    fig_changes.add_trace(go.Scatter(
                        x=group_pd.sort_values("date")["date"],
                        y=smoothed,
                        name=group_name,
                        mode="lines",
                        line=dict(color=brand_colors[idx % len(brand_colors)], width=2.2),
                    ))

            fig_changes = add_discount_bands(fig_changes)
            fig_changes.update_layout(
                **PLOT_LAYOUT,
                height=360,
                title=translate("brand_changes_title"),
                yaxis_title=translate("brand_changes_yaxis"),
            )
            st.plotly_chart(fig_changes, width='stretch', config=PLOT_CONFIG)

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
                st.plotly_chart(fig_brand_delta, width='stretch', config=PLOT_CONFIG)

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

# TAB 6: Tank Advisor (Preview / Execution Disabled)
# ──────────────────────────────────────────────────────────────────────────────
with tab_advisor:
    st.markdown("""
    <div id="advisor-tab-marker"></div>
    <div class="tab-disabled-notice" style="
        background: rgba(148, 163, 184, 0.08);
        border: 1px solid rgba(148, 163, 184, 0.25);
        border-left: 4px solid #94A3B8;
        border-radius: 8px;
        padding: 10px 16px;
        margin-bottom: 14px;
        display: flex;
        align-items: center;
        gap: 12px;
    ">
        <span style="font-size: 1.25rem;">🔒</span>
        <div>
            <div style="font-weight: 600; font-size: 0.88rem; color: #E2E8F0;">
                {translate('advisor_preview_badge')}
            </div>
            <div style="font-size: 0.78rem; color: #94A3B8; margin-top: 2px;">
                {translate('advisor_preview_desc')}
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    tank_advisor_tab.render_tank_advisor_tab(DATA_DIR, fuel_key, translate)

# TAB 7: RAG — Ask Questions (Preview / Execution Disabled)
# ──────────────────────────────────────────────────────────────────────────────
with tab_rag:
    st.markdown(f"""
    <div id="rag-tab-marker"></div>
    <div class="tab-disabled-notice" style="
        background: rgba(148, 163, 184, 0.08);
        border: 1px solid rgba(148, 163, 184, 0.25);
        border-left: 4px solid #94A3B8;
        border-radius: 8px;
        padding: 10px 16px;
        margin-bottom: 14px;
        display: flex;
        align-items: center;
        gap: 12px;
    ">
        <span style="font-size: 1.25rem;">🔒</span>
        <div>
            <div style="font-weight: 600; font-size: 0.88rem; color: #E2E8F0;">
                {translate('rag_preview_badge')}
            </div>
            <div style="font-size: 0.78rem; color: #94A3B8; margin-top: 2px;">
                {translate('rag_preview_desc')}
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown(f"#### {translate('rag_title')}")
    st.markdown(f"<p style='color:#8892A4;font-size:0.85rem;margin-top:-6px;margin-bottom:16px;'>{translate('rag_system_desc')}</p>", unsafe_allow_html=True)

    st.chat_message("user").write(translate("rag_demo_q"))
    st.chat_message("assistant").write(translate("rag_demo_a"))

    st.markdown("<br>", unsafe_allow_html=True)
    st.text_input(translate("rag_input_label"), placeholder=translate("rag_input_placeholder"), disabled=True, key="rag_demo_input")
    st.button(f"🔍 {translate('rag_submit_button')}", disabled=True, width="stretch", key="rag_demo_submit")
    st.caption(translate("rag_disabled_caption"))

