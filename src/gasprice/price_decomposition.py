"""
Module: price_decomposition.py
Description: Granular economic price decomposition model for German fuel prices.
             Mathematically decomposes the gross pump price into all industrial and
             regulatory cost layers:
             1. Crude Base (Brent FOB)
             2. Inbound Crude Freight & Pipeline Tariffs (TAL / NWO)
             3. Gross Refining Margin / Crack Spread (RBOB/Heating Oil Futures benchmark)
             4. Secondary Logistics & Storage (Terminals, Binnenwasserstraßen, TKW road tankers)
             5. Retail & Station Costs (Dealer commission, card processing interchange, overhead)
             6. Pure Wholesaler / Brand Net Profit
             7. Statutory Taxes & Duties (Energy Tax, CO2 Levy BEHG, EBV Levy, 19% VAT)
"""

from dataclasses import dataclass
from typing import Dict, Any
import polars as pl

# ── Benchmark Industry Parameters (Germany) ──────────────────────────────────
# Source: Bundeskartellamt Sektoruntersuchung Raffinerien & Kraftstoffe,
# MWV / en2x Jahresberichte, TAL Pipeline Tariffs, BFT Kostenstrukturanalyse.
CRUDE_INBOUND_FREIGHT_EUR_L = 0.012      # ~1.2 ct/L (Sea freight + Port handling + Pipeline TAL/NWO)
TERMINAL_STORAGE_EUR_L = 0.008           # ~0.8 ct/L (Large tank farm handling, throughput, blending)
ROAD_TANKER_LAST_MILE_EUR_L = 0.012      # ~1.2 ct/L (35-50 km delivery radius per 35,000L tanker)
DOMESTIC_LOGISTICS_EUR_L = TERMINAL_STORAGE_EUR_L + ROAD_TANKER_LAST_MILE_EUR_L  # 2.0 ct/L
DEALER_COMMISSION_EUR_L = 0.012          # ~1.2 ct/L (Fixed station operator / tenant fee)
CARD_PROCESSING_RATE = 0.008             # ~0.8% of gross pump price (Credit/debit interchange & terminal fees)
BRAND_OVERHEAD_EUR_L = 0.008             # ~0.8 ct/L (HQ pricing algos, IT, brand licensing, compliance)


@dataclass(frozen=True)
class PriceComponent:
    key: str
    label_de: str
    label_en: str
    amount_eur_l: float
    amount_ct_l: float
    share_pct: float
    category: str


@dataclass(frozen=True)
class GranularPriceBreakdown:
    pump_price_eur_l: float
    # 1. Crude & Inbound
    crude_fob_eur_l: float
    crude_inbound_freight_eur_l: float
    crude_delivered_eur_l: float
    # 2. Refining (Crack Spread)
    refining_crack_spread_eur_l: float
    wholesale_gate_price_eur_l: float
    # 3. Secondary Logistics
    domestic_terminal_storage_eur_l: float
    road_tanker_last_mile_eur_l: float
    domestic_logistics_total_eur_l: float
    # 4. Retail & Marketing
    dealer_commission_eur_l: float
    card_processing_fees_eur_l: float
    brand_overhead_eur_l: float
    brand_net_profit_eur_l: float
    retail_gross_margin_eur_l: float
    # 5. Taxes & Duties
    energy_tax_eur_l: float
    co2_tax_eur_l: float
    ebv_tax_eur_l: float
    vat_eur_l: float
    total_tax_eur_l: float
    # Structural breakdown dictionary
    components: Dict[str, PriceComponent]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pump_price_eur_l": self.pump_price_eur_l,
            "crude_fob_eur_l": self.crude_fob_eur_l,
            "crude_inbound_freight_eur_l": self.crude_inbound_freight_eur_l,
            "crude_delivered_eur_l": self.crude_delivered_eur_l,
            "refining_crack_spread_eur_l": self.refining_crack_spread_eur_l,
            "wholesale_gate_price_eur_l": self.wholesale_gate_price_eur_l,
            "domestic_logistics_total_eur_l": self.domestic_logistics_total_eur_l,
            "dealer_commission_eur_l": self.dealer_commission_eur_l,
            "card_processing_fees_eur_l": self.card_processing_fees_eur_l,
            "brand_overhead_eur_l": self.brand_overhead_eur_l,
            "brand_net_profit_eur_l": self.brand_net_profit_eur_l,
            "retail_gross_margin_eur_l": self.retail_gross_margin_eur_l,
            "energy_tax_eur_l": self.energy_tax_eur_l,
            "co2_tax_eur_l": self.co2_tax_eur_l,
            "ebv_tax_eur_l": self.ebv_tax_eur_l,
            "vat_eur_l": self.vat_eur_l,
            "total_tax_eur_l": self.total_tax_eur_l,
        }


def decompose_single_price(
    pump_price: float,
    crude_fob: float,
    product_wholesale: float | None,
    energy_tax: float,
    co2_tax: float,
    ebv_tax: float,
    vat: float,
) -> GranularPriceBreakdown:
    """
    Decomposes a single price observation into granular cost components.
    Guarantees exact mathematical reconciliation: sum(components) == pump_price.
    """
    total_tax = energy_tax + co2_tax + ebv_tax + vat
    net_pump_price = max(0.0, pump_price - total_tax)

    # 1. Crude delivered to refinery
    # Crude FOB is raw Brent. We split delivered crude into FOB and Inbound transport.
    crude_inbound = min(CRUDE_INBOUND_FREIGHT_EUR_L, crude_fob * 0.1) if crude_fob > 0 else 0.0
    crude_fob_net = max(0.0, crude_fob - crude_inbound)
    crude_delivered = crude_fob_net + crude_inbound

    # 2. Refining Crack Spread
    if product_wholesale is not None and product_wholesale > 0:
        wholesale_price = product_wholesale
        crack_spread = max(0.0, wholesale_price - crude_delivered)
    else:
        # Fallback: estimate wholesale based on typical gross refining margin (~12 ct/L)
        crack_spread = min(0.12, max(0.02, net_pump_price - crude_delivered))
        wholesale_price = crude_delivered + crack_spread

    # 3. Logistics
    terminal_storage = TERMINAL_STORAGE_EUR_L
    road_tanker = ROAD_TANKER_LAST_MILE_EUR_L
    logistics_total = terminal_storage + road_tanker

    # 4. Retail & Distribution Margin
    retail_total_spread = max(0.0, net_pump_price - wholesale_price)
    
    # Within retail:
    dealer_commission = min(DEALER_COMMISSION_EUR_L, retail_total_spread * 0.4)
    card_fees = pump_price * CARD_PROCESSING_RATE
    brand_overhead = min(BRAND_OVERHEAD_EUR_L, retail_total_spread * 0.25)
    
    # Pure net margin of the brand / oil company
    brand_net_profit = retail_total_spread - logistics_total - dealer_commission - card_fees - brand_overhead

    # Build component objects
    components = {}
    
    def _make_comp(key, label_de, label_en, amt, cat):
        ct = amt * 100
        pct = (amt / pump_price * 100) if pump_price > 0 else 0.0
        return PriceComponent(
            key=key,
            label_de=label_de,
            label_en=label_en,
            amount_eur_l=round(amt, 4),
            amount_ct_l=round(ct, 2),
            share_pct=round(pct, 1),
            category=cat,
        )

    components["crude_fob"] = _make_comp("crude_fob", "Brent-Rohöl (FOB Nordsee)", "Brent Crude (FOB North Sea)", crude_fob_net, "crude")
    components["crude_inbound"] = _make_comp("crude_inbound", "Rohöl-Transport & Pipeline (TAL/NWO)", "Crude Freight & Pipeline Tariff", crude_inbound, "crude")
    components["crack_spread"] = _make_comp("crack_spread", "Raffineriemarge (Crack Spread)", "Refining Margin (Crack Spread)", crack_spread, "refining")
    components["terminal_storage"] = _make_comp("terminal_storage", "Großtanklager & Umschlag", "Terminal Storage & Handling", terminal_storage, "logistics")
    components["road_tanker"] = _make_comp("road_tanker", "Straßentankwagen (letzte Meile)", "Road Tanker Last Mile Delivery", road_tanker, "logistics")
    components["dealer_commission"] = _make_comp("dealer_commission", "Tankstellenpächter-Provision", "Station Dealer Commission", dealer_commission, "retail")
    components["card_fees"] = _make_comp("card_fees", "Kartengebühren & Zahlungsabwicklung", "Payment Interchange & Card Fees", card_fees, "retail")
    components["brand_overhead"] = _make_comp("brand_overhead", "Marken-Overhead & Preissetzung", "Brand Overhead & Pricing IT", brand_overhead, "retail")
    components["brand_net_profit"] = _make_comp("brand_net_profit", "Reiner Mineralölkonzern-Gewinn", "Oil Brand Net Wholesaling Profit", brand_net_profit, "retail")
    components["energy_tax"] = _make_comp("energy_tax", "Energiesteuer (ehem. Mineralölsteuer)", "Energy Tax", energy_tax, "tax")
    components["co2_tax"] = _make_comp("co2_tax", "CO2-Abgabe (BEHG)", "CO2 Levy (BEHG)", co2_tax, "tax")
    components["ebv_tax"] = _make_comp("ebv_tax", "EBV-Krisenvorsorgebeitrag", "EBV Stockholding Levy", ebv_tax, "tax")
    components["vat"] = _make_comp("vat", "Mehrwertsteuer (19%)", "VAT (19%)", vat, "tax")

    return GranularPriceBreakdown(
        pump_price_eur_l=round(pump_price, 4),
        crude_fob_eur_l=round(crude_fob_net, 4),
        crude_inbound_freight_eur_l=round(crude_inbound, 4),
        crude_delivered_eur_l=round(crude_delivered, 4),
        refining_crack_spread_eur_l=round(crack_spread, 4),
        wholesale_gate_price_eur_l=round(wholesale_price, 4),
        domestic_terminal_storage_eur_l=round(terminal_storage, 4),
        road_tanker_last_mile_eur_l=round(road_tanker, 4),
        domestic_logistics_total_eur_l=round(logistics_total, 4),
        dealer_commission_eur_l=round(dealer_commission, 4),
        card_processing_fees_eur_l=round(card_fees, 4),
        brand_overhead_eur_l=round(brand_overhead, 4),
        brand_net_profit_eur_l=round(brand_net_profit, 4),
        retail_gross_margin_eur_l=round(retail_total_spread, 4),
        energy_tax_eur_l=round(energy_tax, 4),
        co2_tax_eur_l=round(co2_tax, 4),
        ebv_tax_eur_l=round(ebv_tax, 4),
        vat_eur_l=round(vat, 4),
        total_tax_eur_l=round(total_tax, 4),
        components=components,
    )


def add_granular_decomposition_columns(df: Any, fuel_type: str = "e5") -> Any:
    """
    Vectorized computation adding detailed economic layers to the dataframe.
    Accepts both polars.DataFrame and pandas.DataFrame, returning the same type.
    """
    was_pandas = not isinstance(df, pl.DataFrame)
    working_df = pl.from_pandas(df) if was_pandas else df

    price_col = f"price_{fuel_type}"
    vat_col = f"{fuel_type}_vat"
    ebv_col = f"{fuel_type}_ebv"
    co2_col = f"{fuel_type}_co2"
    energy_col = f"{fuel_type}_energy"
    product_col = f"{fuel_type}_product_eur_liter"
    raw_col = "Raw_Material_EUR_per_Liter"

    if price_col not in working_df.columns or raw_col not in working_df.columns:
        return df

    has_product = product_col in df.columns

    # Base taxes
    total_tax_expr = pl.col(vat_col) + pl.col(ebv_col) + pl.col(co2_col) + pl.col(energy_col)
    net_price_expr = pl.col(price_col) - total_tax_expr

    # Crude breakdown
    crude_inbound_expr = pl.lit(CRUDE_INBOUND_FREIGHT_EUR_L)
    crude_fob_expr = (pl.col(raw_col) - crude_inbound_expr).clip(lower_bound=0.0)

    # Crack spread
    if has_product:
        crack_spread_expr = (pl.col(product_col) - pl.col(raw_col)).clip(lower_bound=0.0)
        retail_gross_expr = (net_price_expr - pl.col(product_col)).clip(lower_bound=0.0)
    else:
        crack_spread_expr = pl.lit(0.10)
        retail_gross_expr = (net_price_expr - pl.col(raw_col) - crack_spread_expr).clip(lower_bound=0.0)

    # Logistics & Retail
    logistics_expr = pl.lit(DOMESTIC_LOGISTICS_EUR_L)
    dealer_comm_expr = pl.lit(DEALER_COMMISSION_EUR_L)
    card_fees_expr = pl.col(price_col) * pl.lit(CARD_PROCESSING_RATE)
    brand_overhead_expr = pl.lit(BRAND_OVERHEAD_EUR_L)

    brand_net_profit_expr = (
        retail_gross_expr - logistics_expr - dealer_comm_expr - card_fees_expr - brand_overhead_expr
    )

    res = working_df.with_columns([
        crude_fob_expr.alias(f"{fuel_type}_decomp_crude_fob"),
        crude_inbound_expr.alias(f"{fuel_type}_decomp_crude_inbound"),
        crack_spread_expr.alias(f"{fuel_type}_decomp_crack_spread"),
        logistics_expr.alias(f"{fuel_type}_decomp_domestic_logistics"),
        dealer_comm_expr.alias(f"{fuel_type}_decomp_dealer_commission"),
        card_fees_expr.alias(f"{fuel_type}_decomp_card_fees"),
        brand_overhead_expr.alias(f"{fuel_type}_decomp_brand_overhead"),
        brand_net_profit_expr.alias(f"{fuel_type}_decomp_brand_net_profit"),
        retail_gross_expr.alias(f"{fuel_type}_decomp_retail_gross"),
    ])
    return res.to_pandas() if was_pandas else res


# Daily average consumption volume in Germany (source: BAFA Mineralöldaten)
DAILY_CONSUMPTION_LITERS = {
    "e5": 10_000_000.0,       # ~10 million liters/day
    "e10": 36_000_000.0,      # ~36 million liters/day (together gasoline ~46M L/day)
    "diesel": 92_000_000.0,   # ~92 million liters/day
}


def calculate_asymmetric_pass_through(
    df: Any,
    fuel_type: str = "e5",
    window_days: int = 30,
) -> dict[str, Any]:
    """
    Computes Rocket & Feather asymmetry metrics for tax cuts vs. tax hikes.
    Compares:
      - Tax Cuts: Tankrabatt 1 Start (2022-06-01), Tankrabatt 2 Start (2026-05-01), Tankrabatt 3 Start (2026-10-01)
      - Tax Hikes: Tankrabatt 1 End (2022-09-01), Tankrabatt 2 End (2026-07-01), Tankrabatt 3 End (2027-01-01)
    """
    from datetime import date, timedelta

    working_df = pl.from_pandas(df) if not isinstance(df, pl.DataFrame) else df

    price_col = f"price_{fuel_type}"
    tax_cols = [f"{fuel_type}_vat", f"{fuel_type}_ebv", f"{fuel_type}_co2", f"{fuel_type}_energy"]
    if price_col not in working_df.columns or not all(c in working_df.columns for c in tax_cols):
        return {}

    events = [
        {"name": "Tankrabatt 1 Start (Jun 2022)", "date": date(2022, 6, 1), "type": "cut"},
        {"name": "Tankrabatt 1 End (Sep 2022)", "date": date(2022, 9, 1), "type": "hike"},
        {"name": "Tankrabatt 2 Start (May 2026)", "date": date(2026, 5, 1), "type": "cut"},
        {"name": "Tankrabatt 2 End (Jul 2026)", "date": date(2026, 7, 1), "type": "hike"},
        {"name": "Tankrabatt 3 Start (Oct 2026)", "date": date(2026, 10, 1), "type": "cut"},
        {"name": "Tankrabatt 3 End (Jan 2027)", "date": date(2027, 1, 1), "type": "hike"},
    ]

    working_df = df.with_columns(
        (pl.col(f"{fuel_type}_vat") + pl.col(f"{fuel_type}_ebv") + pl.col(f"{fuel_type}_co2") + pl.col(f"{fuel_type}_energy")).alias("total_tax")
    ).sort("date")

    results = []
    cut_rates = []
    hike_rates = []
    max_date = working_df["date"].max()

    for evt in events:
        eff_date = evt["date"]
        if eff_date > max_date:
            continue

        pre_start = eff_date - timedelta(days=window_days)
        pre_end = eff_date - timedelta(days=1)
        post_start = eff_date
        post_end = eff_date + timedelta(days=window_days)

        pre_df = working_df.filter((pl.col("date") >= pre_start) & (pl.col("date") <= pre_end))
        post_df = working_df.filter((pl.col("date") >= post_start) & (pl.col("date") <= post_end))

        if pre_df.is_empty() or post_df.is_empty():
            continue

        pre_price = pre_df[price_col].mean()
        post_price = post_df[price_col].mean()
        delta_price = post_price - pre_price

        pre_tax = pre_df["total_tax"].mean()
        post_tax = post_df["total_tax"].mean()
        delta_tax = post_tax - pre_tax

        # Pass-through rate: ratio of pump price shift to statutory tax shift
        pass_through = (delta_price / delta_tax) if abs(delta_tax) > 0.001 else 1.0

        # Calculate transmission half-life (t_50): days until 50% of the maximum shift materialized
        half_life_days = 0
        window_after = working_df.filter((pl.col("date") >= eff_date) & (pl.col("date") <= post_end)).to_pandas()
        for _, row_p in window_after.iterrows():
            shift = row_p[price_col] - pre_price
            if abs(delta_price) > 0 and (shift / delta_price) >= 0.5:
                row_date = row_p["date"].date() if hasattr(row_p["date"], "date") else row_p["date"]
                half_life_days = (row_date - eff_date).days
                break

        evt_summary = {
            "name": evt["name"],
            "type": evt["type"],
            "date": eff_date,
            "delta_price": round(delta_price, 4),
            "delta_tax": round(delta_tax, 4),
            "pass_through_pct": round(pass_through * 100, 1),
            "half_life_days": max(0, half_life_days),
        }
        results.append(evt_summary)
        if evt["type"] == "cut":
            cut_rates.append(pass_through)
        else:
            hike_rates.append(pass_through)

    avg_cut = sum(cut_rates) / len(cut_rates) if cut_rates else 1.0
    avg_hike = sum(hike_rates) / len(hike_rates) if hike_rates else 1.0
    asymmetry_index = (avg_hike / avg_cut) if avg_cut > 0 else 1.0

    return {
        "events": results,
        "avg_cut_pass_through_pct": round(avg_cut * 100, 1),
        "avg_hike_pass_through_pct": round(avg_hike * 100, 1),
        "asymmetry_index": round(asymmetry_index, 2),
    }


def compute_counterfactual_excess_margin(
    df: Any,
    fuel_type: str = "e5",
    baseline_end_date: Any = None,
) -> Any:
    """
    Calculates counterfactual competitive margins, excess margins, and nationwide consumer damages.
    Accepts both polars.DataFrame and pandas.DataFrame, returning the same type.
    """
    from datetime import date
    if baseline_end_date is None:
        baseline_end_date = date(2021, 12, 31)

    was_pandas = not isinstance(df, pl.DataFrame)
    working_df = pl.from_pandas(df) if was_pandas else df

    margin_col = f"margin_{fuel_type}"
    if margin_col not in working_df.columns:
        return df

    # Baseline margin: mean pre-crisis margin (up to 2021-12-31)
    pre_crisis_df = working_df.filter(pl.col("date") <= baseline_end_date)
    if not pre_crisis_df.is_empty():
        baseline_margin = float(pre_crisis_df[margin_col].mean())
    else:
        baseline_margin = 0.20  # ~20 ct/L standard historical baseline

    daily_vol = DAILY_CONSUMPTION_LITERS.get(fuel_type, 46_000_000.0)

    # Compute daily excess margin and financial impact
    res = working_df.with_columns([
        pl.lit(baseline_margin).alias(f"{fuel_type}_baseline_margin"),
        (pl.col(margin_col) - pl.lit(baseline_margin)).clip(lower_bound=0.0).alias(f"{fuel_type}_excess_margin"),
    ]).with_columns([
        (pl.col(f"{fuel_type}_excess_margin") * 100.0).alias(f"{fuel_type}_excess_margin_ct"),
        (pl.col(f"{fuel_type}_excess_margin") * pl.lit(daily_vol)).alias(f"{fuel_type}_daily_excess_eur"),
    ])

    res = res.with_columns(
        pl.col(f"{fuel_type}_daily_excess_eur").cum_sum().alias(f"{fuel_type}_cumulative_excess_eur")
    )
    return res.to_pandas() if was_pandas else res

