"""
Test Suite: test_price_decomposition.py
Verifies the economic price decomposition model and reconciliation of all cost layers.
"""

import pytest
import polars as pl
from src.gasprice.price_decomposition import (
    decompose_single_price,
    add_granular_decomposition_columns,
)


def test_decompose_single_price_reconciliation():
    """Verify that the sum of all decomposed components equals the pump price."""
    pump_price = 2.159
    crude_fob = 0.550
    product_wholesale = 0.780
    energy_tax = 0.6545
    co2_tax = 0.1547
    ebv_tax = 0.0027
    vat = 0.3447

    breakdown = decompose_single_price(
        pump_price=pump_price,
        crude_fob=crude_fob,
        product_wholesale=product_wholesale,
        energy_tax=energy_tax,
        co2_tax=co2_tax,
        ebv_tax=ebv_tax,
        vat=vat,
    )

    # Check that all components are populated
    assert breakdown.pump_price_eur_l == 2.159
    assert breakdown.crude_delivered_eur_l == pytest.approx(0.550, abs=0.001)
    assert breakdown.refining_crack_spread_eur_l == pytest.approx(0.780 - 0.550, abs=0.001)
    assert breakdown.total_tax_eur_l == pytest.approx(energy_tax + co2_tax + ebv_tax + vat, abs=0.001)

    # Check reconciliation of the dictionary components
    comp_sum = sum(c.amount_eur_l for c in breakdown.components.values())
    assert comp_sum == pytest.approx(pump_price, abs=0.005)


def test_add_granular_decomposition_columns():
    """Verify vectorized Polars decomposition across a DataFrame."""
    df = pl.DataFrame({
        "date": ["2026-06-01", "2026-06-02"],
        "price_e5": [2.20, 2.25],
        "Raw_Material_EUR_per_Liter": [0.55, 0.56],
        "e5_product_eur_liter": [0.75, 0.77],
        "e5_vat": [0.35, 0.36],
        "e5_ebv": [0.003, 0.003],
        "e5_co2": [0.15, 0.15],
        "e5_energy": [0.65, 0.65],
    })

    res = add_granular_decomposition_columns(df, "e5")

    expected_cols = [
        "e5_decomp_crude_fob",
        "e5_decomp_crude_inbound",
        "e5_decomp_crack_spread",
        "e5_decomp_domestic_logistics",
        "e5_decomp_dealer_commission",
        "e5_decomp_card_fees",
        "e5_decomp_brand_overhead",
        "e5_decomp_brand_net_profit",
        "e5_decomp_retail_gross",
    ]
    for col in expected_cols:
        assert col in res.columns
        assert res[col].is_null().sum() == 0


def test_asymmetric_pass_through_and_counterfactual():
    """Verify asymmetric pass-through calculation and counterfactual excess margin model."""
    from datetime import date
    from src.gasprice.price_decomposition import (
        calculate_asymmetric_pass_through,
        compute_counterfactual_excess_margin,
    )

    dates = [date(2022, 5, 20), date(2022, 5, 31), date(2022, 6, 1), date(2022, 6, 15)]
    df = pl.DataFrame({
        "date": dates,
        "price_e5": [2.20, 2.22, 1.95, 1.90],
        "margin_e5": [0.25, 0.26, 0.32, 0.30],
        "e5_vat": [0.35, 0.35, 0.31, 0.30],
        "e5_ebv": [0.003, 0.003, 0.003, 0.003],
        "e5_co2": [0.15, 0.15, 0.15, 0.15],
        "e5_energy": [0.65, 0.65, 0.35, 0.35],
    })

    # Test asymmetric pass-through
    asym = calculate_asymmetric_pass_through(df, fuel_type="e5", window_days=15)
    assert "events" in asym
    assert len(asym["events"]) >= 1
    assert "asymmetry_index" in asym

    # Test counterfactual excess margin
    cf = compute_counterfactual_excess_margin(df, fuel_type="e5", baseline_end_date=date(2022, 5, 25))
    assert "e5_baseline_margin" in cf.columns
    assert "e5_excess_margin" in cf.columns
    assert "e5_daily_excess_eur" in cf.columns
    assert "e5_cumulative_excess_eur" in cf.columns
    assert cf["e5_excess_margin"].min() >= 0.0

