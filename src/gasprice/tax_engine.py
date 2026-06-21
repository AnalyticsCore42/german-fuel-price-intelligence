"""
Module: tax_engine.py
Description: A dynamic, schema-agnostic Polars engine that applies historical German 
             fuel taxes, VAT, CO2 pricing, and EBV contributions to extract the 
             true Net Product Price from any gross pump price.
"""

import polars as pl
from datetime import date
from dataclasses import dataclass

# ==========================================
# 1. SETUP & CONFIGURATION
# ==========================================

EBV_PETROL = 0.0027
EBV_DIESEL = 0.0030

@dataclass(frozen=True)
class VatPeriod:
    start: date
    end: date
    rate: float

@dataclass(frozen=True)
class EnergyTaxPeriod:
    start: date
    end: date
    petrol_rate: float
    diesel_rate: float

@dataclass(frozen=True)
class Co2Period:
    start_year: int
    end_year: int
    petrol_rate: float
    diesel_rate: float

# Declarative historical tax schedules
VAT_PERIODS = [
    VatPeriod(date(2020, 7, 1), date(2020, 12, 31), 0.16)
]
DEFAULT_VAT_RATE = 0.19

ENERGY_TAX_PERIODS = [
    EnergyTaxPeriod(date(2022, 6, 1), date(2022, 8, 31), 0.3590, 0.3300),
    EnergyTaxPeriod(date(2026, 5, 1), date(2026, 6, 30), 0.5141, 0.3300)
]
DEFAULT_PETROL_ENERGY_TAX = 0.6545
DEFAULT_DIESEL_ENERGY_TAX = 0.4704

CO2_PERIODS = [
    Co2Period(2021, 2021, 0.0595, 0.0663),
    Co2Period(2022, 2023, 0.0714, 0.0795),
    Co2Period(2024, 2024, 0.1071, 0.1193),
    Co2Period(2025, 2025, 0.1309, 0.1458),
]
DEFAULT_PETROL_CO2_TAX_2026_PLUS = 0.1547
DEFAULT_DIESEL_CO2_TAX_2026_PLUS = 0.1723

# ==========================================
# 2. TAX ENGINE CORE LOGIC
# ==========================================

def calculate_net_price(
    df: pl.DataFrame, 
    date_col: str, 
    gross_price_col: str, 
    fuel_type: str
) -> pl.DataFrame:
    """
    Applies the historical German tax matrix to calculate the Net Product Price.
    
    Args:
        df: Polars DataFrame
        date_col: Name of the column containing dates or datetimes
        gross_price_col: Name of the column containing the pump price (EUR/Liter)
        fuel_type: 'petrol' or 'diesel'
    """
    fuel_type = fuel_type.lower()
    if fuel_type not in ['petrol', 'diesel']:
        raise ValueError("fuel_type must be either 'petrol' or 'diesel'")

    # Ensure we are working with pure dates for the logic (handles both Date and Datetime columns)
    is_datetime = df.schema[date_col] in [pl.Datetime, pl.Datetime("ms"), pl.Datetime("us"), pl.Datetime("ns")]
    _date = pl.col(date_col).dt.date() if is_datetime else pl.col(date_col)

    # 1. VAT (Mehrwertsteuer) expression construction
    vat_expr = pl.lit(DEFAULT_VAT_RATE)
    for period in VAT_PERIODS:
        vat_expr = pl.when((_date >= period.start) & (_date <= period.end)).then(period.rate).otherwise(vat_expr)

    # 2. EBV Contribution (Erdölbevorratungsverband) expression construction
    ebv_expr = pl.lit(EBV_PETROL if fuel_type == 'petrol' else EBV_DIESEL)

    # 3. CO2 Price (Brennstoffemissionshandelsgesetz) expression construction
    _year = _date.dt.year()
    default_co2 = DEFAULT_PETROL_CO2_TAX_2026_PLUS if fuel_type == 'petrol' else DEFAULT_DIESEL_CO2_TAX_2026_PLUS
    co2_expr = pl.when(_year <= 2020).then(0.0)
    for period in CO2_PERIODS:
        rate = period.petrol_rate if fuel_type == 'petrol' else period.diesel_rate
        co2_expr = co2_expr.when((_year >= period.start_year) & (_year <= period.end_year)).then(rate)
    co2_expr = co2_expr.otherwise(default_co2)

    # 4. Energy Tax (Energiesteuer) expression construction
    default_energy = DEFAULT_PETROL_ENERGY_TAX if fuel_type == 'petrol' else DEFAULT_DIESEL_ENERGY_TAX
    energy_tax_expr = pl.lit(default_energy)
    for period in ENERGY_TAX_PERIODS:
        rate = period.petrol_rate if fuel_type == 'petrol' else period.diesel_rate
        energy_tax_expr = pl.when((_date >= period.start) & (_date <= period.end)).then(rate).otherwise(energy_tax_expr)

    # Apply all expressions to the DataFrame
    df_taxed = df.with_columns([
        vat_expr.alias("VAT_Rate"),
        ebv_expr.alias("EBV_Tax"),
        co2_expr.alias("CO2_Tax"),
        energy_tax_expr.alias("Energy_Tax")
    ])

    # Calculate final Net Product Price: Gross -> strip VAT -> strip fixed taxes = Net Product Price
    df_taxed = df_taxed.with_columns(
        (pl.col(gross_price_col) / (1.0 + pl.col("VAT_Rate"))).alias("Price_Ex_VAT")
    ).with_columns(
        (pl.col("Price_Ex_VAT") - pl.col("Energy_Tax") - pl.col("CO2_Tax") - pl.col("EBV_Tax")).alias("Net_Product_Price")
    )

    return df_taxed

if __name__ == "__main__":
    print("Running Tax Deduction Engine Core Checks...")
    # Create dummy data representing interesting historical edge cases
    dummy_data = pl.DataFrame({
        "timestamp_recorded": [
            date(2020, 6, 30),  # Day before 16% COVID VAT cut
            date(2020, 7, 1),   # First day of 16% COVID VAT cut
            date(2022, 5, 31),  # Day before 1st Fuel Discount (Standard Energy Tax)
            date(2022, 6, 1),   # First day of 1st Fuel Discount (Lower Energy Tax)
            date(2026, 4, 30),  # Day before 2nd Fuel Discount
            date(2026, 5, 1)    # First day of 2nd Fuel Discount
        ],
        "pump_price_e5": [1.40, 1.40, 2.15, 2.15, 1.85, 1.85]
    })
    
    print("\n--- Original Dummy Data ---")
    print(dummy_data)
    
    print("\n--- Applying Tax Engine for 'petrol' ---")
    processed = calculate_net_price(
        df=dummy_data,
        date_col="timestamp_recorded",
        gross_price_col="pump_price_e5",
        fuel_type="petrol"
    )
    
    summary = processed.select([
        "timestamp_recorded", "pump_price_e5", "VAT_Rate", "Energy_Tax", "CO2_Tax", "Net_Product_Price"
    ])
    print(summary)
    print("\nTax Engine Core checks run successfully.")
