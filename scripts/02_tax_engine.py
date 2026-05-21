"""
Script: 03_tax_deduction_engine.py
Description: A dynamic, schema-agnostic Polars engine that applies historical German 
             fuel taxes, VAT, CO2 pricing, and EBV contributions to extract the 
             true Net Product Price from any gross pump price.
Inputs:
    - Any Polars DataFrame containing a Date/Datetime column and a Gross Price column.
Outputs:
    - The same DataFrame with added tax breakdown columns and the final 'Net_Product_Price'.

Memory Constraint: Uses vectorized Polars expressions to maintain <16GB footprint.
"""

import polars as pl
from datetime import date

# ==========================================
# 1. SETUP & CONFIGURATION
# ==========================================

# Constants derived from docs/taxes_and_duties_history.md
EBV_PETROL = 0.0027
EBV_DIESEL = 0.0030

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
    _date = pl.col(date_col).dt.date() if df.schema[date_col] in [pl.Datetime, pl.Datetime("ms"), pl.Datetime("us"), pl.Datetime("ns")] else pl.col(date_col)

    # 1. VAT (Mehrwertsteuer)
    # 16% from July 1, 2020 to Dec 31, 2020. Otherwise 19%.
    vat_expr = pl.when((_date >= date(2020, 7, 1)) & (_date <= date(2020, 12, 31))).then(0.16).otherwise(0.19)

    # 2. EBV Contribution (Erdölbevorratungsverband)
    ebv_expr = pl.lit(EBV_PETROL if fuel_type == 'petrol' else EBV_DIESEL)

    # 3. CO2 Price (Brennstoffemissionshandelsgesetz)
    # Using Scenario B (65 EUR/t) for 2026 and beyond.
    if fuel_type == 'petrol':
        co2_expr = (
            pl.when(_date.dt.year() <= 2020).then(0.00)
            .when(_date.dt.year() == 2021).then(0.0595)
            .when(_date.dt.year().is_in([2022, 2023])).then(0.0714)
            .when(_date.dt.year() == 2024).then(0.1071)
            .when(_date.dt.year() == 2025).then(0.1309)
            .otherwise(0.1547) # 2026+ Scenario B
        )
    else: # diesel
        co2_expr = (
            pl.when(_date.dt.year() <= 2020).then(0.00)
            .when(_date.dt.year() == 2021).then(0.0663)
            .when(_date.dt.year().is_in([2022, 2023])).then(0.0795)
            .when(_date.dt.year() == 2024).then(0.1193)
            .when(_date.dt.year() == 2025).then(0.1458)
            .otherwise(0.1723) # 2026+ Scenario B
        )

    # 4. Energy Tax (Energiesteuer)
    # Handles standard rates and the two Fuel Discount periods.
    discount_1_start, discount_1_end = date(2022, 6, 1), date(2022, 8, 31)
    discount_2_start, discount_2_end = date(2026, 5, 1), date(2026, 6, 30)
    
    if fuel_type == 'petrol':
        energy_tax_expr = (
            pl.when((_date >= discount_1_start) & (_date <= discount_1_end)).then(0.3590)
            .when((_date >= discount_2_start) & (_date <= discount_2_end)).then(0.5141)
            .otherwise(0.6545)
        )
    else: # diesel
        energy_tax_expr = (
            pl.when((_date >= discount_1_start) & (_date <= discount_1_end)).then(0.3300)
            .when((_date >= discount_2_start) & (_date <= discount_2_end)).then(0.3300)
            .otherwise(0.4704)
        )

    # Apply all expressions to the DataFrame
    df_taxed = df.with_columns([
        vat_expr.alias("VAT_Rate"),
        ebv_expr.alias("EBV_Tax"),
        co2_expr.alias("CO2_Tax"),
        energy_tax_expr.alias("Energy_Tax")
    ])

    # Calculate final Net Product Price
    # Gross -> strip VAT -> strip fixed taxes = Net Product Price
    df_taxed = df_taxed.with_columns(
        (pl.col(gross_price_col) / (1.0 + pl.col("VAT_Rate"))).alias("Price_Ex_VAT")
    ).with_columns(
        (pl.col("Price_Ex_VAT") - pl.col("Energy_Tax") - pl.col("CO2_Tax") - pl.col("EBV_Tax")).alias("Net_Product_Price")
    )

    return df_taxed

# ==========================================
# 3. TEST HARNESS
# ==========================================

if __name__ == "__main__":
    print("Running Tax Deduction Engine Tests...")
    
    # Create dummy data representing interesting historical edge cases
    # We will use random column names to prove it's dynamic
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
    
    # Show only the critical columns to easily verify the math
    summary = processed.select([
        "timestamp_recorded", "pump_price_e5", "VAT_Rate", "Energy_Tax", "CO2_Tax", "Net_Product_Price"
    ])
    print(summary)
    
    print("\nTax Engine Test Completed Successfully!")
