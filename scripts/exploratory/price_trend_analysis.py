#!/usr/bin/env python3
"""
Script: price_trend_analysis.py
Description: Comprehensive price trend analysis with ML modeling.
             Covers: 12am price rule, price change patterns, ML time series model.
"""

import polars as pl
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# Configuration resolved dynamically relative to project root
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
PRICES_DIR = DATA_DIR / "tankerkoenig" / "prices"
MACRO_FILE = DATA_DIR / "processed_macro_baseline.parquet"

def load_price_data(year=2026, month=None):
    """Load price data for specified year/month or all available data"""
    files = sorted(PRICES_DIR.glob(f"{year}/*.parquet"))
    if month:
        files = [f for f in files if f"{year}-{month:02d}" in str(f)]

    all_data = []
    for f in files:
        df = pl.read_parquet(f)
        all_data.append(df)

    if all_data:
        return pl.concat(all_data)
    return pl.DataFrame()

def load_macro_data():
    """Load macro baseline data"""
    df = pl.read_parquet(MACRO_FILE)
    return df

def analyze_12am_rule(df):
    """Analyze the 12am price change rule"""
    print("=" * 60)
    print("1. 12AM PRICE RULE ANALYSIS")
    print("=" * 60)

    # Get data around midnight
    hourly_avg = df.group_by([
        pl.col("date").dt.hour().alias("hour"),
        pl.col("date").dt.date().alias("date_date")
    ]).agg([
        pl.col("e5").mean().alias("e5_avg"),
        pl.col("e10").mean().alias("e10_avg"),
        pl.col("diesel").mean().alias("diesel_avg"),
    ]).sort(["date_date", "hour"])

    # Calculate price change at midnight (hour 0)
    midnight_changes = []
    dates = hourly_avg["date_date"].unique().sort()

    for date in dates:
        prev_day = date - timedelta(days=1)
        prev_data = hourly_avg.filter(
            (pl.col("date_date") == prev_day) & (pl.col("hour") == 23)
        )
        curr_data = hourly_avg.filter(
            (pl.col("date_date") == date) & (pl.col("hour") == 0)
        )

        if not prev_data.is_empty() and not curr_data.is_empty():
            prev_e5 = prev_data["e5_avg"].item()
            curr_e5 = curr_data["e5_avg"].item()
            change = curr_e5 - prev_e5

            midnight_changes.append({
                "date": date,
                "prev_23h_e5": prev_e5,
                "midnight_0h_e5": curr_e5,
                "change": change,
            })

    midnight_df = pd.DataFrame(midnight_changes)

    print("\nMidnight (00:00) Price Change Analysis:")
    print("-" * 50)
    print(f"Total days analyzed: {len(midnight_df)}")

    if not midnight_df.empty:
        print(f"\nMidnight price changes (E5):")
        print(f"  Mean change: {midnight_df['change'].mean():+.4f} €/L")
        print(f"  Std dev:     {midnight_df['change'].std():.4f} €/L")
        print(f"  Min change:  {midnight_df['change'].min():+.4f} €/L")
        print(f"  Max change:  {midnight_df['change'].max():+.4f} €/L")

        # Calculate how often price increases at midnight
        increases = (midnight_df['change'] > 0).sum()
        decreases = (midnight_df['change'] < 0).sum()
        no_change = (midnight_df['change'] == 0).sum()

        print(f"\nDirection distribution:")
        print(f"  Increases at midnight: {increases} ({increases/len(midnight_df)*100:.1f}%)")
        print(f"  Decreases at midnight: {decreases} ({decreases/len(midnight_df)*100:.1f}%)")
        print(f"  No change:             {no_change}")

        print(f"\nDay-of-week analysis of midnight changes:")
        midnight_df['day_of_week'] = pd.to_datetime(midnight_df['date']).dt.day_name()
        day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        for day in day_order:
            day_data = midnight_df[midnight_df['day_of_week'] == day]
            if not day_data.empty:
                print(f"  {day:<10}: {day_data['change'].mean():+.4f} €/L (n={len(day_data)})")

    return midnight_df

def analyze_price_change_patterns(df):
    """Analyze patterns in price changes"""
    print("\n" + "=" * 60)
    print("2. PRICE CHANGE PATTERN ANALYSIS")
    print("=" * 60)

    # Time between changes
    df_sorted = df.sort(["station_uuid", "date"])

    print("\nE5 Price Change Distribution:")
    print("-" * 50)
    e5_changes = df_sorted.select(["date", "station_uuid", "e5", "e5change"])
    e5_changes_pd = e5_changes.to_pandas()

    # Analyze change magnitude
    print(f"  Total observations: {len(e5_changes_pd):,}")
    print(f"  Station changes (e5change=1): {(e5_changes_pd['e5change'] == 1).sum():,}")
    print(f"  Increase distribution:")
    print(f"    +1€ct:  {(e5_changes_pd['e5change'] == 1).sum():,} ({(e5_changes_pd['e5change'] == 1).sum()/len(e5_changes_pd)*100:.1f}%)")
    print(f"    +2€ct:  {(e5_changes_pd['e5change'] == 2).sum():,} ({(e5_changes_pd['e5change'] == 2).sum()/len(e5_changes_pd)*100:.1f}%)")
    print(f"    +3€ct:  {(e5_changes_pd['e5change'] == 3).sum():,} ({(e5_changes_pd['e5change'] == 3).sum()/len(e5_changes_pd)*100:.1f}%)")
    print(f"    Other:  {(e5_changes_pd['e5change'] > 3).sum():,}")

    # Hourly price change frequency
    print("\nHourly price change frequency (E5):")
    print("-" * 50)
    e5_changes_pd['hour'] = pd.to_datetime(e5_changes_pd['date']).dt.hour
    hour_changes = e5_changes_pd.groupby('hour').agg({
        'e5change': lambda x: (x > 0).sum()
    }).reset_index()
    hour_changes.columns = ['hour', 'change_count']

    for _, row in hour_changes.iterrows():
        bar = "█" * int(row['change_count'] / 50)
        print(f"  {row['hour']:02d}:00 | {bar} {row['change_count']}")

    # Calculate average E5 by hour
    print("\nAverage E5 price by hour of day:")
    print("-" * 50)
    hourly_avg = df_sorted.group_by(pl.col("date").dt.hour().alias("hour")).agg([
        pl.col("e5").mean().alias("e5_avg"),
        pl.col("e10").mean().alias("e10_avg"),
        pl.col("diesel").mean().alias("diesel_avg"),
    ]).sort("hour")

    for row in hourly_avg.iter_rows():
        hour, e5_avg, e10_avg, diesel_avg = row
        print(f"  {hour:02d}:00 | E5: {e5_avg:.3f} | E10: {e10_avg:.3f} | Diesel: {diesel_avg:.3f}")

    return hour_changes

def analyze_price_vs_brent(df, macro_df):
    """Analyze price relationship with Brent crude"""
    print("\n" + "=" * 60)
    print("3. PRICE vs BRENT CRUDE ANALYSIS")
    print("=" * 60)

    # Calculate daily averages
    daily_avg = df.group_by(pl.col("date").dt.date().alias("date")).agg([
        pl.col("e5").mean().alias("e5"),
        pl.col("e10").mean().alias("e10"),
        pl.col("diesel").mean().alias("diesel"),
    ]).sort("date")

    # Get macro data for same period
    macro = macro_df.select(["date", "Raw_Material_EUR_per_Liter", "DEXUSEU"])
    macro = macro.rename({"DEXUSEU": "EUR_USD_rate"})

    # Merge
    merged = daily_avg.join(macro, on="date", how="inner")

    # Convert to pandas for feature engineering
    merged_pd = merged.to_pandas()
    merged_pd['date'] = pd.to_datetime(merged_pd['date'])
    merged_pd = merged_pd.sort_values('date').reset_index(drop=True)

    print("\nE5 vs Brent Correlation (daily):")
    print("-" * 50)

    if merged_pd.shape[0] > 10:
        e5_vals = merged_pd["e5"].values
        brent_vals = merged_pd["Raw_Material_EUR_per_Liter"].values

        if len(e5_vals) == len(brent_vals):
            corr = np.corrcoef(e5_vals, brent_vals)[0, 1]
            print(f"  Correlation (E5 vs Brent): {corr:.4f}")

            # Calculate spread
            spread = e5_vals - brent_vals
            print(f"\n  E5-Brent Spread:")
            print(f"    Mean: {spread.mean():+.4f} €/L")
            print(f"    Std:  {spread.std():.4f} €/L")
            print(f"    Min:  {spread.min():+.4f} €/L")
            print(f"    Max:  {spread.max():+.4f} €/L")

    # Analyze price response lag
    print("\nPrice response analysis (day-by-day Brent change vs E5 change):")
    print("-" * 50)

    if merged_pd.shape[0] > 5:
        merged_pd['brent_change'] = merged_pd['Raw_Material_EUR_per_Liter'].diff()
        merged_pd['e5_change'] = merged_pd['e5'].diff()

        # Correlation at different lags
        for lag in [0, 1, 2, 3, 4, 5]:
            shifted_brent = merged_pd['brent_change'].shift(lag)
            valid_mask = shifted_brent.notna() & merged_pd['e5_change'].notna()

            if valid_mask.sum() > 10:
                corr = merged_pd.loc[valid_mask, 'e5_change'].corr(shifted_brent[valid_mask])
                print(f"  Lag {lag} day(s): correlation = {corr:.4f}")

    return merged_pd

def prepare_ml_features(df, macro_df):
    """Prepare features for ML modeling"""
    print("\n" + "=" * 60)
    print("4. MACHINE LEARNING FEATURE ENGINEERING")
    print("=" * 60)

    # Daily aggregated prices
    daily_avg = df.group_by(pl.col("date").dt.date().alias("date")).agg([
        pl.col("e5").mean().alias("e5"),
        pl.col("e10").mean().alias("e10"),
        pl.col("diesel").mean().alias("diesel"),
        pl.col("station_uuid").n_unique().alias("n_stations"),
    ]).sort("date")

    # Merge with macro data
    macro = macro_df.select(["date", "Raw_Material_EUR_per_Liter", "DEXUSEU"])
    macro = macro.rename({"DEXUSEU": "EUR_USD_rate"})
    merged = daily_avg.join(macro, on="date", how="inner")

    # Convert to pandas for feature engineering
    merged_pd = merged.to_pandas()
    merged_pd['date'] = pd.to_datetime(merged_pd['date'])
    merged_pd = merged_pd.sort_values('date').reset_index(drop=True)

    # Create features
    print("\nCreating features for ML model:")
    print("-" * 40)

    # 1. Time features
    merged_pd['day_of_week'] = merged_pd['date'].dt.dayofweek
    merged_pd['day_of_month'] = merged_pd['date'].dt.day
    merged_pd['month'] = merged_pd['date'].dt.month
    merged_pd['year'] = merged_pd['date'].dt.year
    print("  ✓ Time features (day_of_week, day_of_month, month, year)")

    # 2. Lag features (previous day prices)
    for col in ['e5', 'e10', 'diesel', 'Raw_Material_EUR_per_Liter']:
        for lag in [1, 2, 3]:
            merged_pd[f'{col}_lag{lag}'] = merged_pd[col].shift(lag)
    print("  ✓ Lag features (price and Brent from 1-3 days ago)")

    # 3. Rolling window features
    for col in ['e5', 'e10', 'diesel', 'Raw_Material_EUR_per_Liter']:
        merged_pd[f'{col}_rolling_mean_7'] = merged_pd[col].rolling(7, min_periods=1).mean()
        merged_pd[f'{col}_rolling_mean_14'] = merged_pd[col].rolling(14, min_periods=1).mean()
        merged_pd[f'{col}_rolling_std_7'] = merged_pd[col].rolling(7, min_periods=1).std()
    print("  ✓ Rolling mean and std (7 and 14 day windows)")

    # 4. Price change features
    for col in ['e5', 'e10', 'diesel']:
        merged_pd[f'{col}_change'] = merged_pd[col].diff()
        merged_pd[f'{col}_pct_change'] = merged_pd[col].pct_change()
    print("  ✓ Price change features")

    # 5. Brent gap (spread)
    merged_pd['brent_gap_e5'] = merged_pd['e5'] - merged_pd['Raw_Material_EUR_per_Liter']
    merged_pd['brent_gap_e10'] = merged_pd['e10'] - merged_pd['Raw_Material_EUR_per_Liter']
    merged_pd['brent_gap_diesel'] = merged_pd['diesel'] - merged_pd['Raw_Material_EUR_per_Liter']
    print("  ✓ Brent gap features (spread over raw material)")

    # 6. Interaction features
    merged_pd['brent_x_eurusd'] = merged_pd['Raw_Material_EUR_per_Liter'] * merged_pd['EUR_USD_rate']
    print("  ✓ Interaction features (Brent × EUR/USD)")

    # 7. Tax-break period indicators
    merged_pd['is_tax_break_2022'] = ((merged_pd['date'] >= '2022-06-01') &
                                      (merged_pd['date'] <= '2022-08-31')).astype(int)
    merged_pd['is_tax_break_2026'] = ((merged_pd['date'] >= '2026-05-01') &
                                      (merged_pd['date'] <= '2026-06-30')).astype(int)

    # One-hot encode day of week
    day_dummies = pd.get_dummies(merged_pd['day_of_week'], prefix='dow', drop_first=True)
    merged_pd = pd.concat([merged_pd, day_dummies], axis=1)
    print("  ✓ Tax-break period indicators and day-of-week dummies")

    print(f"\nFinal dataset: {merged_pd.shape[0]} rows, {merged_pd.shape[1]} columns")
    return merged_pd

def run_ml_model(merged_pd):
    """Run ML models on the prepared features"""
    print("\n" + "=" * 60)
    print("5. MACHINE LEARNING MODELING (Time Series)")
    print("=" * 60)

    from sklearn.preprocessing import StandardScaler
    from sklearn.linear_model import LinearRegression
    from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

    # Select target and features
    target = 'e5'  # Predict E5 price

    # Drop rows with NaN (due to shifting/lags)
    merged_clean = merged_pd.dropna()

    # Feature columns
    feature_cols = [col for col in merged_clean.columns if col not in
                    ['date', 'e5', 'e10', 'diesel', 'day_of_week'] and not col.startswith('dow_')]

    # Also add day of week dummies
    feature_cols.extend([col for col in merged_clean.columns if col.startswith('dow_')])

    # Split data (time-based split for time series)
    X = merged_clean[feature_cols]
    y = merged_clean[target]

    # Time-based split (80% train, 20% test)
    split_idx = int(len(X) * 0.8)
    X_train, X_test = X[:split_idx], X[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]

    print(f"\nTrain set: {len(X_train)} days")
    print(f"Test set:  {len(X_test)} days")

    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # Initialize models
    models = {
        'Linear Regression': LinearRegression(),
        'Random Forest': RandomForestRegressor(n_estimators=100, random_state=42),
        'Gradient Boosted Trees': GradientBoostingRegressor(
            n_estimators=100, learning_rate=0.1, random_state=42
        ),
    }

    print("\nModel Results:")
    print("-" * 70)
    print(f"{'Model':<25} | {'MAE':>8} | {'RMSE':>8} | {'R² Score':>8}")
    print("-" * 70)

    for name, model in models.items():
        X_tr = X_train_scaled
        X_te = X_test_scaled

        model.fit(X_tr, y_train)
        y_pred = model.predict(X_te)

        mae = mean_absolute_error(y_test, y_pred)
        rmse = np.sqrt(mean_squared_error(y_test, y_pred))
        r2 = r2_score(y_test, y_pred)

        print(f"{name:<25} | {mae:>8.4f} | {rmse:>8.4f} | {r2:>8.4f}")

        # Feature importance (if available)
        if hasattr(model, 'feature_importances_'):
            importances = sorted(zip(feature_cols, model.feature_importances_),
                                 key=lambda x: x[1], reverse=True)
            print(f"\n  Top 10 features for {name}:")
            for feat, imp in importances[:10]:
                print(f"    {feat:<35} {imp:.4f}")

    print("-" * 70)

    return models, merged_clean, X_test, y_test, scaler

def main():
    print("Loading price data...")
    df = load_price_data(2026)
    if df.is_empty():
        print("Warning: price dataset is empty.")
        return
        
    print(f"Loaded {len(df):,} price records")

    print("\nLoading macro data...")
    macro_df = load_macro_data()
    print(f"Loaded {len(macro_df):,} macro records")

    # 1. Analyze 12am rule
    midnight_df = analyze_12am_rule(df)

    # 2. Analyze price change patterns
    hour_changes = analyze_price_change_patterns(df)

    # 3. Analyze price vs Brent
    price_vs_brent = analyze_price_vs_brent(df, macro_df)

    # 4. Prepare ML features
    merged_pd = prepare_ml_features(df, macro_df)

    # 5. Run ML models
    models, merged_clean, X_test, y_test, scaler = run_ml_model(merged_pd)

if __name__ == "__main__":
    main()
