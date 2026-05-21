"""
Test Suite: test_tax_engine.py
Tests the core tax deduction engine (scripts/02_tax_engine.py) which is the mathematical
foundation of every margin and spread calculation in the project.

Run with:  pytest tests/ -v
Coverage:  pytest tests/ --cov=scripts --cov-report=term-missing

Priority: HIGH — wrong tax rates mean every downstream analysis is wrong.
"""

import sys
from pathlib import Path
from datetime import date

import polars as pl
import pytest

# Add scripts/ to path so we can import directly
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from importlib import import_module
tax_engine = import_module("02_tax_engine")
calculate_net_price = tax_engine.calculate_net_price


# ==========================================
# 1. HELPERS
# ==========================================

def make_df(dates: list[date], prices: list[float]) -> pl.DataFrame:
    """Build a minimal test DataFrame."""
    return pl.DataFrame({
        "date": dates,
        "gross": prices,
    })


def calc(dates, prices, fuel_type="petrol"):
    """Shortcut: run the engine and return the result DataFrame."""
    df = make_df(dates, prices)
    return calculate_net_price(df, "date", "gross", fuel_type)


def net(dates, prices, fuel_type="petrol") -> list[float]:
    """Return just the Net_Product_Price values as a list of floats."""
    result = calc(dates, prices, fuel_type)
    return result["Net_Product_Price"].to_list()


def tax_col(dates, prices, col_name, fuel_type="petrol") -> list[float]:
    """Return a specific tax column as a list."""
    result = calc(dates, prices, fuel_type)
    return result[col_name].to_list()


# ==========================================
# 2. INPUT VALIDATION
# ==========================================

class TestInputValidation:
    def test_invalid_fuel_type_raises(self):
        with pytest.raises(ValueError, match="petrol.*diesel"):
            calc([date(2023, 1, 1)], [1.80], fuel_type="benzin")

    def test_petrol_accepted(self):
        result = calc([date(2023, 1, 1)], [1.80], fuel_type="petrol")
        assert "Net_Product_Price" in result.columns

    def test_diesel_accepted(self):
        result = calc([date(2023, 1, 1)], [1.80], fuel_type="diesel")
        assert "Net_Product_Price" in result.columns

    def test_case_insensitive(self):
        result = calc([date(2023, 1, 1)], [1.80], fuel_type="PETROL")
        assert "Net_Product_Price" in result.columns


# ==========================================
# 3. VAT RATES
# ==========================================

class TestVATRates:
    """VAT was temporarily 16% from 2020-07-01 to 2020-12-31, otherwise 19%."""

    def test_standard_vat_before_covid(self):
        rates = tax_col([date(2020, 6, 30)], [1.50], "VAT_Rate")
        assert rates[0] == pytest.approx(0.19)

    def test_covid_vat_first_day(self):
        rates = tax_col([date(2020, 7, 1)], [1.50], "VAT_Rate")
        assert rates[0] == pytest.approx(0.16)

    def test_covid_vat_last_day(self):
        rates = tax_col([date(2020, 12, 31)], [1.50], "VAT_Rate")
        assert rates[0] == pytest.approx(0.16)

    def test_standard_vat_after_covid(self):
        rates = tax_col([date(2021, 1, 1)], [1.50], "VAT_Rate")
        assert rates[0] == pytest.approx(0.19)

    def test_standard_vat_2024(self):
        rates = tax_col([date(2024, 6, 15)], [1.80], "VAT_Rate")
        assert rates[0] == pytest.approx(0.19)


# ==========================================
# 4. ENERGY TAX — PETROL
# ==========================================

class TestEnergyTaxPetrol:
    """
    Petrol energy tax:
      Standard:         €0.6545/L
      Tankrabatt 1:     €0.3590/L  (2022-06-01 to 2022-08-31)
      Tankrabatt 2:     €0.5141/L  (2026-05-01 to 2026-06-30)
    """

    def test_standard_rate_before_discount_1(self):
        rates = tax_col([date(2022, 5, 31)], [2.00], "Energy_Tax", "petrol")
        assert rates[0] == pytest.approx(0.6545)

    def test_discount_1_first_day(self):
        rates = tax_col([date(2022, 6, 1)], [2.00], "Energy_Tax", "petrol")
        assert rates[0] == pytest.approx(0.3590)

    def test_discount_1_last_day(self):
        rates = tax_col([date(2022, 8, 31)], [2.00], "Energy_Tax", "petrol")
        assert rates[0] == pytest.approx(0.3590)

    def test_standard_rate_after_discount_1(self):
        rates = tax_col([date(2022, 9, 1)], [2.00], "Energy_Tax", "petrol")
        assert rates[0] == pytest.approx(0.6545)

    def test_standard_rate_between_discounts(self):
        rates = tax_col([date(2025, 1, 1)], [2.00], "Energy_Tax", "petrol")
        assert rates[0] == pytest.approx(0.6545)

    def test_discount_2_day_before(self):
        rates = tax_col([date(2026, 4, 30)], [2.00], "Energy_Tax", "petrol")
        assert rates[0] == pytest.approx(0.6545)

    def test_discount_2_first_day(self):
        rates = tax_col([date(2026, 5, 1)], [2.00], "Energy_Tax", "petrol")
        assert rates[0] == pytest.approx(0.5141)

    def test_discount_2_last_day(self):
        rates = tax_col([date(2026, 6, 30)], [2.00], "Energy_Tax", "petrol")
        assert rates[0] == pytest.approx(0.5141)

    def test_standard_rate_after_discount_2(self):
        rates = tax_col([date(2026, 7, 1)], [2.00], "Energy_Tax", "petrol")
        assert rates[0] == pytest.approx(0.6545)


# ==========================================
# 5. ENERGY TAX — DIESEL
# ==========================================

class TestEnergyTaxDiesel:
    """
    Diesel energy tax:
      Standard:         €0.4704/L
      Tankrabatt 1:     €0.3300/L  (2022-06-01 to 2022-08-31)
      Tankrabatt 2:     €0.3300/L  (2026-05-01 to 2026-06-30) — same as Tankrabatt 1!
    """

    def test_standard_rate(self):
        rates = tax_col([date(2022, 5, 31)], [1.80], "Energy_Tax", "diesel")
        assert rates[0] == pytest.approx(0.4704)

    def test_discount_1_first_day(self):
        rates = tax_col([date(2022, 6, 1)], [1.80], "Energy_Tax", "diesel")
        assert rates[0] == pytest.approx(0.3300)

    def test_discount_1_last_day(self):
        rates = tax_col([date(2022, 8, 31)], [1.80], "Energy_Tax", "diesel")
        assert rates[0] == pytest.approx(0.3300)

    def test_standard_after_discount_1(self):
        rates = tax_col([date(2022, 9, 1)], [1.80], "Energy_Tax", "diesel")
        assert rates[0] == pytest.approx(0.4704)

    def test_discount_2_first_day(self):
        rates = tax_col([date(2026, 5, 1)], [1.80], "Energy_Tax", "diesel")
        assert rates[0] == pytest.approx(0.3300)

    def test_discount_2_last_day(self):
        rates = tax_col([date(2026, 6, 30)], [1.80], "Energy_Tax", "diesel")
        assert rates[0] == pytest.approx(0.3300)

    def test_standard_after_discount_2(self):
        rates = tax_col([date(2026, 7, 1)], [1.80], "Energy_Tax", "diesel")
        assert rates[0] == pytest.approx(0.4704)


# ==========================================
# 6. CO2 TAX
# ==========================================

class TestCO2Tax:
    """CO2 prices scale year by year. Verify the step function."""

    @pytest.mark.parametrize("year,expected", [
        (2019, 0.0000),
        (2020, 0.0000),
        (2021, 0.0595),
        (2022, 0.0714),
        (2023, 0.0714),
        (2024, 0.1071),
        (2025, 0.1309),
        (2026, 0.1547),
        (2027, 0.1547),  # 2026+ fallback
    ])
    def test_co2_petrol(self, year, expected):
        rates = tax_col([date(year, 6, 15)], [2.00], "CO2_Tax", "petrol")
        assert rates[0] == pytest.approx(expected, abs=1e-4)

    @pytest.mark.parametrize("year,expected", [
        (2019, 0.0000),
        (2020, 0.0000),
        (2021, 0.0663),
        (2022, 0.0795),
        (2024, 0.1193),
        (2025, 0.1458),
        (2026, 0.1723),
    ])
    def test_co2_diesel(self, year, expected):
        rates = tax_col([date(year, 6, 15)], [2.00], "CO2_Tax", "diesel")
        assert rates[0] == pytest.approx(expected, abs=1e-4)


# ==========================================
# 7. EBV TAX
# ==========================================

class TestEBV:
    def test_petrol_ebv(self):
        rates = tax_col([date(2024, 1, 1)], [2.00], "EBV_Tax", "petrol")
        assert rates[0] == pytest.approx(0.0027)

    def test_diesel_ebv(self):
        rates = tax_col([date(2024, 1, 1)], [2.00], "EBV_Tax", "diesel")
        assert rates[0] == pytest.approx(0.0030)


# ==========================================
# 8. END-TO-END NET PRICE MATH
# ==========================================

class TestNetPriceMath:
    """
    Verify the full calculation: Gross / (1 + VAT) - Energy - CO2 - EBV = Net
    Hand-calculated reference values.
    """

    def test_petrol_standard_2024(self):
        """
        Gross = €1.80
        VAT 19%: 1.80 / 1.19 = 1.51261
        Energy: 0.6545
        CO2: 0.1071
        EBV: 0.0027
        Net = 1.51261 - 0.6545 - 0.1071 - 0.0027 = 0.74831
        """
        vals = net([date(2024, 6, 15)], [1.80], "petrol")
        expected = 1.80 / 1.19 - 0.6545 - 0.1071 - 0.0027
        assert vals[0] == pytest.approx(expected, abs=1e-4)

    def test_petrol_during_discount_1(self):
        """
        Gross = €2.00, date 2022-07-15 (inside Tankrabatt 1)
        VAT 19%: 2.00 / 1.19 = 1.68067
        Energy: 0.3590  (discounted!)
        CO2: 0.0714  (2022 rate)
        EBV: 0.0027
        Net = 1.68067 - 0.3590 - 0.0714 - 0.0027 = 1.24757
        """
        vals = net([date(2022, 7, 15)], [2.00], "petrol")
        expected = 2.00 / 1.19 - 0.3590 - 0.0714 - 0.0027
        assert vals[0] == pytest.approx(expected, abs=1e-4)

    def test_diesel_during_discount_2(self):
        """
        Gross = €1.60, date 2026-05-15 (inside Tankrabatt 2)
        VAT 19%: 1.60 / 1.19 = 1.34454
        Energy: 0.3300  (discounted)
        CO2: 0.1723  (2026 rate for diesel)
        EBV: 0.0030
        Net = 1.34454 - 0.3300 - 0.1723 - 0.0030 = 0.83924
        """
        vals = net([date(2026, 5, 15)], [1.60], "diesel")
        expected = 1.60 / 1.19 - 0.3300 - 0.1723 - 0.0030
        assert vals[0] == pytest.approx(expected, abs=1e-4)

    def test_covid_vat_affects_net(self):
        """Same gross price, different VAT → different net."""
        before_covid = net([date(2020, 6, 30)], [1.40], "petrol")[0]
        during_covid = net([date(2020, 7, 1)], [1.40], "petrol")[0]
        # 16% VAT → higher net than 19% VAT (less tax stripped)
        assert during_covid > before_covid


# ==========================================
# 9. BOUNDARY DAY TRANSITIONS
# ==========================================

class TestBoundaryTransitions:
    """
    The critical edge cases: the day BEFORE and the day OF each policy change.
    If these boundaries are off by even 1 day, all event study analysis is wrong.
    """

    def test_tankrabatt_1_boundary_petrol(self):
        """May 31 = standard, June 1 = discounted. Energy tax must drop by 0.2955."""
        day_before = tax_col([date(2022, 5, 31)], [2.00], "Energy_Tax", "petrol")[0]
        day_of     = tax_col([date(2022, 6, 1)],  [2.00], "Energy_Tax", "petrol")[0]
        assert day_before - day_of == pytest.approx(0.2955, abs=1e-4)

    def test_tankrabatt_1_end_boundary_petrol(self):
        """Aug 31 = discounted, Sep 1 = standard. Energy tax must jump by 0.2955."""
        last_day  = tax_col([date(2022, 8, 31)], [2.00], "Energy_Tax", "petrol")[0]
        next_day  = tax_col([date(2022, 9, 1)],  [2.00], "Energy_Tax", "petrol")[0]
        assert next_day - last_day == pytest.approx(0.2955, abs=1e-4)

    def test_tankrabatt_2_boundary_petrol(self):
        """Apr 30 = standard, May 1 = discounted. Energy tax must drop by 0.1404."""
        day_before = tax_col([date(2026, 4, 30)], [2.00], "Energy_Tax", "petrol")[0]
        day_of     = tax_col([date(2026, 5, 1)],  [2.00], "Energy_Tax", "petrol")[0]
        assert day_before - day_of == pytest.approx(0.1404, abs=1e-4)

    def test_tankrabatt_2_end_boundary_petrol(self):
        """Jun 30 = discounted, Jul 1 = standard."""
        last_day = tax_col([date(2026, 6, 30)], [2.00], "Energy_Tax", "petrol")[0]
        next_day = tax_col([date(2026, 7, 1)],  [2.00], "Energy_Tax", "petrol")[0]
        assert next_day - last_day == pytest.approx(0.1404, abs=1e-4)

    def test_tankrabatt_1_boundary_diesel(self):
        """Diesel cut = 0.1404 at Tankrabatt 1 start."""
        day_before = tax_col([date(2022, 5, 31)], [1.80], "Energy_Tax", "diesel")[0]
        day_of     = tax_col([date(2022, 6, 1)],  [1.80], "Energy_Tax", "diesel")[0]
        assert day_before - day_of == pytest.approx(0.1404, abs=1e-4)

    def test_diesel_discount_2_same_as_discount_1(self):
        """Diesel Tankrabatt 2 uses the SAME 0.33 rate as Tankrabatt 1."""
        d1_rate = tax_col([date(2022, 7, 1)],  [1.80], "Energy_Tax", "diesel")[0]
        d2_rate = tax_col([date(2026, 5, 15)], [1.80], "Energy_Tax", "diesel")[0]
        assert d1_rate == pytest.approx(d2_rate)


# ==========================================
# 10. OUTPUT SCHEMA
# ==========================================

class TestOutputSchema:
    """Verify all expected columns are present and no NaNs sneak in."""

    def test_all_columns_present(self):
        result = calc([date(2024, 1, 1)], [1.80])
        expected_cols = {"VAT_Rate", "EBV_Tax", "CO2_Tax", "Energy_Tax",
                         "Price_Ex_VAT", "Net_Product_Price"}
        assert expected_cols.issubset(set(result.columns))

    def test_no_nulls_in_output(self):
        dates = [date(2020, 1, 1), date(2022, 6, 1), date(2026, 5, 1)]
        result = calc(dates, [1.50, 2.00, 1.80])
        for col in ["VAT_Rate", "EBV_Tax", "CO2_Tax", "Energy_Tax", "Net_Product_Price"]:
            assert result[col].null_count() == 0, f"Null found in {col}"

    def test_net_price_always_positive(self):
        """Net price should be positive for any reasonable pump price."""
        dates = [date(2024, 1, 1)] * 3
        prices = [1.20, 1.80, 2.50]
        vals = net(dates, prices)
        assert all(v > 0 for v in vals), f"Negative net price found: {vals}"
