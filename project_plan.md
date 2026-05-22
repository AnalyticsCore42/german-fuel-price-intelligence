Project Plan
Last updated: 2026-05-21

## Phase 1: Project Setup & Documentation ✅
- [x] Initialize repository and folder structure (`/data`, `/docs`, `/scripts`, `/scripts/validation`, `/ui`)
- [x] Document tax constants: `docs/taxes_and_duties_history.md`
- [x] Document policy timeline: `docs/policy_timeline_tankrabatt.md` (legislative milestone dates for both Tankrabatte)
- [x] Document brand, group, and ownership ground truth: `docs/market_structure.md`
- [x] Define and maintain this project plan

## Phase 2: Data Collection & Validation ✅
- [x] Fuel station prices (intraday): historical CSV dumps from Tankerkönig/MTS-K, 2021–2026
- [x] Brent Crude Oil prices: seed baseline from EIA (`data/seed_bulk_baseline_brent_crude.csv`), live updates via Yahoo Finance JSON API
- [x] EUR/USD exchange rate: seed baseline from ECB (`data/seed_bulk_baseline_eur_usd.csv`), live updates via Yahoo Finance JSON API
- [x] Data validation scripts in `scripts/validation/`:
  - `01_validate_macro_data.py` — checks Brent/FX data integrity
  - `02_analyze_raw_data.py` — raw pump price sanity checks
  - `03_analyze_stations.py` — station-level coverage checks
  - `04_price_trend_analysis.py` — price trend validation

## Phase 3: Data Processing & ETL ✅
- [x] `scripts/01_update_brent_crude.py` — incremental live update of Brent + EUR/USD, writes `data/processed_macro_baseline.parquet`
- [x] `scripts/02_tax_engine.py` — vectorized tax deduction engine (VAT, Energy Tax, CO2, EBV), handles all historical rate changes including both Tankrabatte
- [x] `scripts/03_download_pump_prices.py` — Tankerkönig intraday data ingestion
- [x] `scripts/05_fetch_refined_product_baseline.py` — fetches 20-year history of refined products (`RB=F`, `HO=F`, `EH=F`) and `EURUSD=X` from Yahoo, applies metric conversions and bioethanol blends, and outputs aligned `data/processed_refined_product_baseline.parquet`
- [x] `scripts/04_build_dashboard_dataset.py` — joins macro + refined product + pump prices, applies tax engine, outputs:
  - `data/processed_daily_margins.parquet` (national daily averages + net product spreads + crack spreads + retail margins)
  - `data/processed_intraday.parquet` (intraday patterns for daily rhythm analysis)
  - `data/processed_brand_daily_margins.parquet` (daily brand/ownership margin comparisons + crack spreads + retail margins)

## Phase 4: Dashboard & Visualization ✅ (ongoing)
- [x] Streamlit dashboard (`ui/04_app.py`) with English/German language toggle
- [x] **Spread Baseline Mode** — dynamic toggle between Brent Crude (Total Spreads) and Refined Product (Pure Retail Margins)
- [x] **Procurement Smoothing Engine** — sidebar control to apply rolling window averages (Daily, 7d, 14d, 30d) simulating long-term supply/inventory contracts using parallel vectorized Polars over-partitions
- [x] Tab 1: Brent vs. Pump — raw material cost vs. pump price with tax breakdown overlay and dynamic three-layered stacked charts (Brent $\rightarrow$ Refining spread $\rightarrow$ Retail margin $\rightarrow$ Taxes)
- [x] Tab 2: Net Product Spread — margin analysis with:
  - [x] Fuel Tax Break Pass-Through bar chart and table
  - [x] Event Study Timeline Chart (single-event selectbox, ±45d window, normalized/absolute toggle)
  - [x] Policy milestone markers from official legislative dates
  - [x] Auto-generated data-driven verdict per event
- [x] Tab 3: Daily Rhythm — intraday price patterns by time of day
- [x] Tab 4: Brand Comparison — compare margins by visible brand buckets (50+ stations, smaller brands grouped) or corporate ownership groups
- [x] `start_dashboard.py` — IDE-runnable Python launcher for Streamlit server

## Phase 5: Planned / Future

1. ~~pytest suite for `scripts/02_tax_engine.py`~~ ✅ Done — 56 tests, run with `pytest tests/ -v`
2. ~~Brand comparison — compare margins and pricing behavior across gas station brands (Shell, Aral, Jet, etc.) in general and specifically during the Tankrabatt periods~~ ✅ Done — `data/processed_brand_daily_margins.parquet` + dashboard tab
3. RAG pipeline evaluation — text-to-SQL over the parquet files via DuckDB + LLM tool-calling, to enable natural language queries on price/margin data
4. Deploy to Streamlit Cloud or self-hosted server
5. Write the rest of the tests (Low Priority)

## Test Coverage

Coverage is tracked automatically via `pytest-cov`. Every `pytest` run prints a per-file report:

```
pytest tests/ -v
```

Config: `pytest.ini` + `.coveragerc` (omits IO-only scripts and validation scripts).
