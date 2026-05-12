"""
Script: 04_app.py
Description: Premium Streamlit dashboard for German Gasoline Prices Analysis.
             Uses real macro data (Brent/EUR-USD baseline) + vectorized mock retail data.
             Swap out mock generation with real Tankerkönig data when it arrives.
Inputs:  ../data/processed_macro_baseline_1999_2026.parquet
Outputs: Interactive dark-mode dashboard on http://localhost:8501
"""

import streamlit as st
import polars as pl
import plotly.graph_objects as go
import plotly.express as px
from datetime import date
from pathlib import Path

# Resolve data path relative to this script file — works from any working directory
DATA_DIR = Path(__file__).parent.parent / "data"

# ==========================================
# 1. SETUP & CONFIGURATION
# ==========================================

st.set_page_config(
    page_title="⛽ Tankpreise Analyse — Germany",
    page_icon="⛽",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={"About": "German Fuel Corporate Margin Analysis — Phase 4 Dashboard"}
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
    .kpi-label  { font-size: 0.78rem; color: #8892A4; letter-spacing: 0.06em; text-transform: uppercase; margin-bottom: 6px; }
    .kpi-value  { font-size: 1.9rem; font-weight: 700; color: #E8EAF0; line-height: 1; }
    .kpi-delta  { font-size: 0.8rem; margin-top: 6px; }
    .kpi-delta.up   { color: #F5A623; }
    .kpi-delta.down { color: #22C55E; }
    .kpi-delta.bad  { color: #EF4444; }

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
    margin=dict(l=10, r=10, t=40, b=10),
    hovermode="x unified",
    hoverlabel=dict(bgcolor="#121929", bordercolor="#2A3347", font_size=13),
    legend=dict(bgcolor="rgba(0,0,0,0)", bordercolor="rgba(0,0,0,0)"),
    xaxis=dict(gridcolor="rgba(255,255,255,0.05)", showline=False),
    yaxis=dict(gridcolor="rgba(255,255,255,0.05)", showline=False),
)

ACCENT      = "#F5A623"   # amber / energy
ACCENT_ALT  = "#22C55E"   # green / positive margin
DANGER      = "#EF4444"   # red / warning
BLUE        = "#3B82F6"   # blue / reference

# Fuel Discount periods
DISCOUNT_PERIODS = [
    ("2022-06-01", "2022-08-31", "1st Fuel Discount (Tankrabatt 1)"),
    ("2026-05-01", "2026-06-30", "2nd Fuel Discount (Tankrabatt 2)"),
]

# ==========================================
# 2. DATA PIPELINE (Vectorized — no loops)
# ==========================================

@st.cache_data(show_spinner="Loading aggregated margins + taxes…")
def load_data(start_date: date = date(2021, 1, 1)):
    """
    Loads the real aggregated daily margins (Tankerkönig + Macro).
    """
    df = pl.read_parquet(DATA_DIR / "processed_daily_margins_2021_2026.parquet")
    df = df.filter(pl.col("date") >= start_date)
    return df

# ── Intraday mock (static, not date-dependent) ────────────────────────────────
@st.cache_data
def get_intraday_data():
    hours  = list(range(24))
    # Realistic German pattern: cheap night, rises to 12pm peak, drops 18-22, cheap again
    prices = [
        1.74, 1.72, 1.71, 1.70, 1.70, 1.71,  # 00–05 night cheap
        1.73, 1.77, 1.82, 1.87, 1.91, 1.96,  # 06–11 rising
        1.97, 1.96, 1.94, 1.92, 1.91, 1.90,  # 12–17 plateau (12pm spike)
        1.88, 1.83, 1.79, 1.76, 1.74, 1.72,  # 18–23 evening drop
    ]
    return pl.DataFrame({"Hour": hours, "Avg_Price_EUR": prices})

@st.cache_data
def get_geo_data():
    return pl.DataFrame({
        "Location":  ["Autobahn",  "City Centre", "Suburbs",  "Rural"],
        "Avg_Price": [2.14,         1.87,          1.82,       1.76],
        "Stations":  [1_800,        12_400,        8_600,      6_200],
    })

# ==========================================
# 3. SIDEBAR — Controls
# ==========================================

with st.sidebar:
    st.markdown("## ⛽ Tankpreise")
    st.markdown("<div style='color:#8892A4;font-size:0.8rem;margin-bottom:16px;'>Germany Fuel Margin Analysis</div>", unsafe_allow_html=True)
    st.divider()

    df_full = load_data()
    # Polars 1.x returns a native Python date scalar directly — no .to_python() needed
    raw_min = df_full["date"].min()
    raw_max = df_full["date"].max()
    min_d = raw_min.to_python() if hasattr(raw_min, 'to_python') else raw_min
    max_d = raw_max.to_python() if hasattr(raw_max, 'to_python') else raw_max

    date_range = st.slider(
        "Date Range",
        min_value=min_d, max_value=max_d,
        value=(date(2022, 1, 1), max_d),
        help="Filter all charts to this date window"
    )

    fuel_type = st.selectbox(
        "Fuel Type",
        ["Super E5", "Super E10", "Diesel"],
        index=0
    )

    tax_viz = st.selectbox(
        "Tax Visualization (Tab 1)",
        ["Hide Taxes", "Total Taxes (Combined)", "Taxes (Detailed Breakdown)"],
        index=2,
        help="Visualize how taxes bridge the gap between raw material cost and the pump price."
    )

    st.divider()
    st.markdown("<div style='color:#4A5568;font-size:0.72rem;margin-top:auto;padding-top:24px;'>Data: EIA · ECB · Tankerkönig</div>", unsafe_allow_html=True)

# ==========================================
# 4. MAIN AREA
# ==========================================

st.markdown("## German Fuel Price — Corporate Margin Tracker")
st.markdown("<div style='color:#8892A4;margin-bottom:24px;'>Where did the 2022 & 2026 fuel tax discounts actually go?</div>", unsafe_allow_html=True)

# Filter based on sidebar date range
df = df_full.filter(
    (pl.col("date") >= date_range[0]) & (pl.col("date") <= date_range[1])
).to_pandas()

# Map fuel type selection to column names
col_map = {
    "Super E5": {
        "price": "price_e5", "margin": "margin_e5", "net": "e5_net_price",
        "vat": "e5_vat", "ebv": "e5_ebv", "co2": "e5_co2", "energy": "e5_energy"
    },
    "Super E10": {
        "price": "price_e10", "margin": "margin_e10", "net": "e10_net_price",
        "vat": "e10_vat", "ebv": "e10_ebv", "co2": "e10_co2", "energy": "e10_energy"
    },
    "Diesel": {
        "price": "price_diesel", "margin": "margin_diesel", "net": "diesel_net_price",
        "vat": "diesel_vat", "ebv": "diesel_ebv", "co2": "diesel_co2", "energy": "diesel_energy"
    }
}
p_col = col_map[fuel_type]["price"]
m_col = col_map[fuel_type]["margin"]
vat_col = col_map[fuel_type]["vat"]
ebv_col = col_map[fuel_type]["ebv"]
co2_col = col_map[fuel_type]["co2"]
energy_col = col_map[fuel_type]["energy"]

# Calculate total tax for the "Combined" view
df["total_tax"] = df[vat_col] + df[ebv_col] + df[co2_col] + df[energy_col]

# Calculate correlation (lagged by 2 days)
if len(df) > 10:
    corr_df = df_full.select(["Raw_Material_EUR_per_Liter", p_col]).drop_nulls().to_pandas()
    # Shift Brent by 2 days forward to align past Brent with today's Pump
    corr_val = corr_df["Raw_Material_EUR_per_Liter"].shift(2).corr(corr_df[p_col])
else:
    corr_val = 0.0

# ── KPI Row ──────────────────────────────────────────────────────────────────
kpi1, kpi2, kpi3, kpi4 = st.columns(4)

current_raw  = df["Raw_Material_EUR_per_Liter"].iloc[-1]
current_pump = df[p_col].iloc[-1]
current_marg = df[m_col].iloc[-1]

pre_disc  = df[df["date"] < "2022-06-01"][m_col].mean()
disc_marg = df[(df["date"] >= "2022-06-01") & (df["date"] <= "2022-08-31")][m_col].mean()
delta_marg = disc_marg - pre_disc if not (pre_disc != pre_disc) else 0  # nan-safe

with kpi1:
    st.markdown(f"""<div class='kpi-card'>
        <div class='kpi-label'>Brent Crude (EUR/L)</div>
        <div class='kpi-value'>€{current_raw:.3f}</div>
        <div class='kpi-delta up'>Raw Material Cost</div>
    </div>""", unsafe_allow_html=True)

with kpi2:
    st.markdown(f"""<div class='kpi-card'>
        <div class='kpi-label'>Pump Price ({fuel_type})</div>
        <div class='kpi-value'>€{current_pump:.3f}</div>
        <div class='kpi-delta'>National Average</div>
    </div>""", unsafe_allow_html=True)

with kpi3:
    delta_class = "bad" if current_marg > 0.10 else "down"
    st.markdown(f"""<div class='kpi-card'>
        <div class='kpi-label'>Corporate Margin</div>
        <div class='kpi-value'>€{current_marg:.3f}</div>
        <div class='kpi-delta {delta_class}'>Net of Taxes &amp; Raw Material</div>
    </div>""", unsafe_allow_html=True)

with kpi4:
    sign = "+" if delta_marg > 0 else ""
    cls  = "bad" if delta_marg > 0 else "down"
    st.markdown(f"""<div class='kpi-card'>
        <div class='kpi-label'>Margin Δ During Discount 1</div>
        <div class='kpi-value'>{sign}€{delta_marg:.3f}</div>
        <div class='kpi-delta {cls}'>Pre-discount baseline compared</div>
    </div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── Tabs ────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs([
    "📈  Brent vs Pump",
    "💰  Corporate Margin",
    "⏱️  Daily Rhythm",
    "🗺️  Location Premium",
])

# ── Helper: Add Discount Highlight Bands ─────────────────────────────────────
def add_discount_bands(fig):
    colors = ["rgba(245,166,35,0.12)", "rgba(59,130,246,0.10)"]
    for (x0, x1, label), color in zip(DISCOUNT_PERIODS, colors):
        if x0 >= df["date"].astype(str).min() or x1 <= df["date"].astype(str).max():
            fig.add_vrect(
                x0=x0, x1=x1, fillcolor=color, opacity=1,
                layer="below", line_width=1, line_color="rgba(245,166,35,0.3)",
                annotation_text=label,
                annotation_position="top left",
                annotation_font=dict(color="#F5A623", size=11),
            )
    return fig

# ──────────────────────────────────────────────────────────────────────────────
# TAB 1: Brent vs Pump
# ──────────────────────────────────────────────────────────────────────────────
with tab1:
    with st.container():
        st.markdown(f"#### Retail Pump Price vs. Raw Brent Crude — {fuel_type}")
        st.markdown("<span style='color:#8892A4;font-size:0.85rem;'>The gap between the two lines is where taxes and corporate margins live. Watch what happens to the gap during the discount bands.</span>", unsafe_allow_html=True)

        fig = go.Figure()
        
        # Base Layer: Brent Crude
        fig.add_trace(go.Scatter(
            x=df["date"], y=df["Raw_Material_EUR_per_Liter"],
            name="Brent (EUR/L)", 
            mode="lines",
            fill="tozeroy" if tax_viz == "Hide Taxes" else None,
            fillcolor="rgba(34,197,94,0.08)" if tax_viz == "Hide Taxes" else None,
            line=dict(color=ACCENT_ALT, width=2),
            stackgroup="one" if tax_viz != "Hide Taxes" else None
        ))
        
        if tax_viz == "Total Taxes (Combined)":
            fig.add_trace(go.Scatter(
                x=df["date"], y=df["total_tax"],
                name="Total Taxes",
                mode="lines",
                line=dict(width=0),
                fillcolor="rgba(100, 116, 139, 0.4)", # Slate-500
                stackgroup="one",
                hovertemplate="Total Tax: €%{y:.3f}<extra></extra>"
            ))
            
        elif tax_viz == "Taxes (Detailed Breakdown)":
            # Plot in order from bottom to top: EBV -> CO2 -> Energy -> VAT
            # using a cohesive slate/indigo gradient
            tax_layers = [
                (ebv_col, "EBV Contribution", "rgba(51, 65, 85, 0.6)"),       # Slate-700
                (co2_col, "CO₂ Pricing", "rgba(71, 85, 105, 0.6)"),            # Slate-600
                (energy_col, "Energy Tax", "rgba(100, 116, 139, 0.6)"),        # Slate-500
                (vat_col, "Value Added Tax (VAT)", "rgba(148, 163, 184, 0.6)") # Slate-400
            ]
            
            for col, name, color in tax_layers:
                fig.add_trace(go.Scatter(
                    x=df["date"], y=df[col],
                    name=name,
                    mode="lines",
                    line=dict(width=0),
                    fillcolor=color,
                    stackgroup="one",
                    hovertemplate=name + ": €%{y:.3f}<extra></extra>"
                ))

        # Top Layer: Pump Price (Independent line, not stacked)
        fig.add_trace(go.Scatter(
            x=df["date"], y=df[p_col],
            name=f"Pump Price — {fuel_type}",
            mode="lines",
            line=dict(color=ACCENT, width=2.5),
        ))
        
        fig = add_discount_bands(fig)
        
        # Determine max Y axis to keep charts stable
        max_y = df[p_col].max() * 1.1
        fig.update_layout(**PLOT_LAYOUT, height=480, yaxis_title="€ / Liter", yaxis_range=[0, max_y])
        st.plotly_chart(fig, use_container_width=True)

        if corr_val != 0.0:
            st.markdown(f"<div style='text-align:right; font-size:0.85rem; color:#8892A4;'>Pearson Correlation (2-day lag): <strong>{corr_val*100:.1f}%</strong></div>", unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────────────
# TAB 2: Corporate Margin
# ──────────────────────────────────────────────────────────────────────────────
with tab2:
    st.markdown("#### Isolated Corporate Margin Over Time")
    st.markdown("<span style='color:#8892A4;font-size:0.85rem;'>After stripping VAT, Energy Tax, CO₂, and EBV — what profit per liter does the oil company keep?</span>", unsafe_allow_html=True)

    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(
        x=df["date"], y=df[m_col],
        name="Corporate Margin", fill="tozeroy",
        fillcolor="rgba(245,166,35,0.07)",
        line=dict(color=ACCENT, width=2.5),
    ))
    # Baseline reference line
    baseline = df[m_col].mean()
    fig2.add_hline(y=baseline, line_dash="dot", line_color=BLUE, line_width=1,
                   annotation_text=f" Historical avg: €{baseline:.3f}", annotation_font_color=BLUE)
    fig2 = add_discount_bands(fig2)
    fig2.update_layout(**PLOT_LAYOUT, height=400, yaxis_title="Corporate Margin (€/L)")
    st.plotly_chart(fig2, use_container_width=True)

    # Sub-metrics below chart
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Pre-Discount Avg", f"€{pre_disc:.4f}")
    with c2:
        sign = "+" if delta_marg > 0 else ""
        st.metric("During Discount 1", f"€{disc_marg:.4f}", f"{sign}€{delta_marg:.4f}", delta_color="inverse")
    with c3:
        st.metric("Historical Range", f"€{df['Mock_Corporate_Margin'].min():.3f} – €{df['Mock_Corporate_Margin'].max():.3f}")

# ──────────────────────────────────────────────────────────────────────────────
# TAB 3: Daily Rhythm
# ──────────────────────────────────────────────────────────────────────────────
with tab3:
    st.markdown("#### Average Price by Hour of Day")
    st.markdown("<span style='color:#8892A4;font-size:0.85rem;'>Oil companies use central pricing algorithms to systematically raise prices during commute hours and cut them at night to attract late-night impulse customers.</span>", unsafe_allow_html=True)

    intraday = get_intraday_data().to_pandas()
    min_h  = intraday["Avg_Price_EUR"].min()
    max_h  = intraday["Avg_Price_EUR"].max()
    best_h = intraday.loc[intraday["Avg_Price_EUR"].idxmin(), "Hour"]
    worst_h = intraday.loc[intraday["Avg_Price_EUR"].idxmax(), "Hour"]

    fig3 = go.Figure()
    fig3.add_trace(go.Scatter(
        x=intraday["Hour"], y=intraday["Avg_Price_EUR"],
        name="Avg Price", mode="lines+markers",
        fill="tozeroy", fillcolor="rgba(59,130,246,0.07)",
        line=dict(color=BLUE, width=3),
        marker=dict(size=7, color=BLUE),
    ))
    fig3.add_annotation(x=worst_h, y=max_h + 0.005, text=f"⚠️ Peak {worst_h:02d}:00 (€{max_h:.2f})", showarrow=True, arrowhead=2, arrowcolor=DANGER, font=dict(color=DANGER))
    fig3.add_annotation(x=best_h, y=min_h - 0.01, text=f"✅ Cheapest {best_h:02d}:00 (€{min_h:.2f})", showarrow=True, arrowhead=2, arrowcolor=ACCENT_ALT, font=dict(color=ACCENT_ALT))
    fig3.update_layout(**PLOT_LAYOUT, height=400, xaxis_title="Hour of Day", yaxis_title="Avg Pump Price (€/L)")
    fig3.update_xaxes(tickmode="linear", dtick=2, gridcolor="rgba(255,255,255,0.05)")
    st.plotly_chart(fig3, use_container_width=True)

    st.info(f"💡 **Best time to fill up:** around {best_h:02d}:00 (saves ~€{(max_h - min_h):.2f}/L vs. the {worst_h:02d}:00 peak). Over 50L that is ~**€{50*(max_h-min_h):.1f}** per tank.")

# ──────────────────────────────────────────────────────────────────────────────
# TAB 4: Location Premium
# ──────────────────────────────────────────────────────────────────────────────
with tab4:
    st.markdown("#### Price Premium by Station Location Type")
    st.markdown("<span style='color:#8892A4;font-size:0.85rem;'>Autobahn stations exploit captive motorists with no alternative. Rural and suburban stations compete more aggressively.</span>", unsafe_allow_html=True)

    geo = get_geo_data().to_pandas()
    fig4 = go.Figure(go.Bar(
        x=geo["Location"],
        y=geo["Avg_Price"],
        marker_color=[DANGER, ACCENT, BLUE, ACCENT_ALT],
        text=[f"€{p:.2f}" for p in geo["Avg_Price"]],
        textposition="outside",
        textfont=dict(color="#E8EAF0", size=14),
    ))
    cheapest = geo["Avg_Price"].min()
    fig4.add_hline(y=cheapest, line_dash="dot", line_color=ACCENT_ALT, line_width=1,
                   annotation_text=f" Rural baseline: €{cheapest:.2f}", annotation_font_color=ACCENT_ALT)
    fig4.update_layout(**PLOT_LAYOUT, height=380, yaxis_title="Avg Price (€/L)", showlegend=False)
    fig4.update_yaxes(range=[1.65, 2.25], gridcolor="rgba(255,255,255,0.05)")
    st.plotly_chart(fig4, use_container_width=True)

    c1, c2 = st.columns(2)
    autobahn = geo.loc[geo["Location"] == "Autobahn", "Avg_Price"].values[0]
    rural    = geo.loc[geo["Location"] == "Rural",    "Avg_Price"].values[0]
    with c1:
        st.metric("Autobahn Premium vs Rural", f"+€{(autobahn - rural):.2f}/L", f"+{((autobahn/rural - 1)*100):.1f}%", delta_color="inverse")
    with c2:
        st.metric("Cost per 50L Tank (Autobahn vs Rural)", f"€{50*(autobahn - rural):.1f} extra", "Captive demand pricing")
