Project Plan
Last updated: 2026-07-05

## Recent Changes
- Added **Tank Advisor** tab (`ui/tank_advisor_tab.py`, `src/gasprice/tank_advisor.py`) with browser geolocation, Nominatim geocoding, Folium map, and driving-cost model.
- Fixed Tank Advisor **round-trip driving cost bug**: the model now charges fuel for both directions of the detour, preventing absurd far-away recommendations.
- Switched Tank Advisor to **point-in-time raw prices** from `data/tankerkoenig/prices/{YYYY}/{YYYY-MM-DD}.parquet`: it loads the last observation per station up to the user-selected date/time, filtering out stale/bogus single observations that produced €1.00/L recommendations.
- Added **browser geolocation** (via `streamlit-js-eval`) and **Photon address autocomplete** with city names and postcodes to the Tank Advisor location input.
- Added **savings projection** in €/month and €/year with adjustable monthly driving distance, comparing recommended vs. closest and vs. most expensive station.
- Switched dashboard national average to **station-count-weighted** aggregation using `processed_regional_daily_margins.parquet`; population weighting was tested and found equivalent.
- Added **brand price-change frequency** metrics (`changes_diesel/e5/e10`) and a chart in the Brand Comparison tab.
- Added pipeline **quality checks**: date gaps, low-reporting hours, price outliers, extreme single-day jumps, and brand change-frequency sanity checks.
- Added configurable memory management (`MAX_RAM_GB`, `POLARS_FORCE_MALLOC=1`, dynamic batch sizing) to the dashboard dataset builder.
- Added **unit tests** for `build_dashboard_dataset.py` and `tank_advisor.py`.
- Added **data dictionary** (`docs/data_dictionary.md`) and **agent context** (`AGENTS.md`).
- Cleaned up 115 macOS `._*` / `.DS_Store` files.

## Phase 1: Project Setup & Documentation ✅
- [x] Initialize repository and folder structure (`/data`, `/docs`, `/scripts`, `/scripts/exploratory`, `/src`, `/tests`, `/ui`)
- [x] Document tax constants: `docs/taxes_and_duties_history.md`
- [x] Document policy timeline: `docs/policy_timeline_tankrabatt.md` (legislative milestone dates for both Tankrabatte)
- [x] Document brand, group, and ownership ground truth: `docs/market_structure.md`
- [x] Coding guidelines: `CODING_GUIDELINES.md`
- [x] Define and maintain this project plan

## Phase 2: Data Collection & Validation ✅
- [x] Fuel station prices (intraday): historical parquet dumps from Tankerkönig/MTS-K, 2021–2026
- [x] Brent Crude Oil prices: seed baseline from EIA (`data/seed_bulk_baseline_brent_crude.csv`), live updates via Yahoo Finance JSON API
- [x] EUR/USD exchange rate: seed baseline from ECB (`data/seed_bulk_baseline_eur_usd.csv`), live updates via Yahoo Finance JSON API
- [x] Exploratory / validation scripts in `scripts/exploratory/`:
  - `validate_macro_data.py` — checks Brent/FX data integrity
  - `analyze_raw_data.py` — raw pump price sanity checks
  - `analyze_stations.py` — station-level coverage checks
  - `price_trend_analysis.py` — price trend validation
  - `analyze_aral_pricing.py` — deep-dive into ARAL pricing patterns
  - `compare_national_weighting.py` — empirical comparison of national-average weighting schemes

## Phase 3: Data Processing & ETL ✅
- [x] `src/gasprice/update_brent_crude.py` — incremental live update of Brent + EUR/USD, writes `data/processed_macro_baseline.parquet`
- [x] `src/gasprice/tax_engine.py` — vectorized tax deduction engine (VAT, Energy Tax, CO2, EBV), handles all historical rate changes including both Tankrabatte
- [x] `src/gasprice/download_pump_prices.py` — Tankerkönig intraday data ingestion
- [x] `src/gasprice/fetch_refined_product_baseline.py` — fetches 20-year history of refined products (`RB=F`, `HO=F`, `EH=F`) and `EURUSD=X` from Yahoo, applies metric conversions and bioethanol blends, and outputs aligned `data/processed_refined_product_baseline.parquet`
- [x] `src/gasprice/clean_stations.py` — cleans station metadata and maps corporate groups / postcode regions
- [x] `src/gasprice/build_dashboard_dataset.py` — joins macro + refined product + pump prices, applies tax engine, supports incremental rebuilds, runs quality checks, and outputs:
  - `data/processed_daily_margins.parquet` (national daily averages + net product spreads + retail margins)
  - `data/processed_intraday.parquet` (intraday patterns for daily rhythm analysis)
  - `data/processed_brand_daily_margins.parquet` (daily brand/ownership margin comparisons + change frequency)
  - `data/processed_regional_daily_margins.parquet` (daily regional margin comparisons + station counts)
- [x] Memory management: dynamic batch sizing, `POLARS_FORCE_MALLOC=1`, configurable RAM limit
- [x] Quality checks: date gaps, low-reporting hours, price outliers, extreme single-day jumps, brand change-frequency sanity checks

## Phase 4: Dashboard & Visualization ✅
- [x] Streamlit dashboard (`ui/04_app.py`) with English/German language toggle
- [x] **Spread Baseline Mode** — dynamic toggle between Brent Crude (Total Spreads) and Refined Product (Pure Retail Margins)
- [x] **Procurement Smoothing Engine** — sidebar control to apply rolling window averages (Daily, 7d, 14d, 30d) simulating long-term supply/inventory contracts using parallel vectorized Polars over-partitions
- [x] Tab 1: Brent vs. Pump — raw material cost vs. pump price with tax breakdown overlay and dynamic three-layered stacked charts
- [x] Tab 2: Net Product Spread — margin analysis with fuel-tax pass-through, event-study timeline, and policy milestone markers
- [x] Tab 3: Daily Rhythm — intraday price patterns by time of day
- [x] Tab 4: Brand Comparison — compare margins and price-change frequency by visible brand buckets or corporate ownership groups
- [x] Tab 5: Regional Pricing — regional price deviations from the national average
- [x] Tab 6: Tank Advisor (`ui/tank_advisor_tab.py` + `src/gasprice/tank_advisor.py`) — location-aware station recommender with geocoding, Folium map, and driving-cost model
- [x] National average now uses station-count weighting (computed from `processed_regional_daily_margins.parquet`) for a more representative national price
- [x] `start_dashboard.py` — IDE-runnable Python launcher for Streamlit server

## Phase 5: Testing ✅
- [x] `tests/test_tax_engine.py` — 56 tests for tax calculations
- [x] `tests/test_tank_advisor.py` — tests for geocoding, distance, cost model, and map generation
- [x] `tests/test_ui_app.py` — smoke test for Streamlit dashboard import
- [x] Coverage tracked automatically via `pytest-cov`:

```bash
pytest tests/ -v
```

Config: `pytest.ini` + `.coveragerc` (omits IO-only scripts and validation scripts).

## Phase 6: Planned / Future
1. **Spatial Brand Analysis** — compute local pricing premiums by comparing each station's price relative to its 10–30 geographically closest neighbors (BallTree/Haversine) to eliminate Autobahn vs. countryside captive-pricing skew.
2. **ML Forecasting Layer** — train LightGBM models on station-level or regional features to predict short-term price movements and pass-through effects.
3. **RAG Pipeline** — text-to-SQL over the parquet files via DuckDB + LLM tool-calling, to enable natural language queries on price/margin data.
4. **Code Quality** — add tests for `build_dashboard_dataset.py` and `download_pump_prices.py`; consider splitting very large modules (`build_dashboard_dataset.py`, `ui/04_app.py`) into smaller files.
5. **Deployment** — keep Cloud Run deployment up to date (`docs/gcp_deployment.md`).
6. **GitHub Repo Link** — add a source-code link to the dashboard footer and/or the local `PROJECT_LINKS.md` file once the repo visibility (public/private) is decided.
