Project Plan
Last updated: 2026-09-19

## Status & Plan for Today (2026-09-19)

### ✅ Done Today
1. **12-Uhr-Regel Compliance & "Name & Shame" Audit (`tab_compliance`):**
   - Built empirical audit of the statutory single 12:00 price hike rule (KPAnG).
   - Conservative classification with a 13:00 buffer (11:55–13:00) to account for data transmission delays vs. deliberate multi-hike violators (stations that already hiked at 12:00 and hiked again later).
   - Refuted the drift hypothesis: Offender share did NOT rise over time (no erosion of compliance), but fell from 31.4% in April to 21.6% in September (-31.2% decline).
   - Built full Streamlit audit tab with 3 KPI cards, daily drift bar chart + 7d trend, brand violation comparison, 2-digit PLZ Leitbereich ranking, filterable station table, and transparency disclaimer (*).
   - Precomputed datasets: `data/dashboard/compliance_daily_trend.parquet` and `data/dashboard/compliance_station_rankings.parquet`.

2. **Top Discount KPI Cards Mathematical Reconciliation & Validation Checks (`ui/04_app.py`):**
   - Enforced strict economic identity: $\text{Steuersenkung} = \text{Weitergegeben} + \text{Einbehalten (Kosten \& Marge)}$.
   - Guaranteed numbers strictly add up to 100% of the tax cut across all fuels and periods.
   - Fixed the Diesel 2026 distortion (previously 164% due to post-Iran war crude collapse): Isolated pure tax transmission via the immediate 14-day event window around May 1, 2026 (yielding 84% pass-through, 13.7 ct/L passed, +2.5 ct/L retained).
   - Added automated anomaly detection and validation checks: If raw pump drop exceeds statutory tax cut due to concurrent crude collapse, an alert notice is displayed detailing the unadjusted vs. adjusted transmission.
   - Added automated pytest suite: `test_discount_kpi_cards_mathematical_reconciliation_and_validation` verifying $0\% \le \text{pass\_pct} \le 100\%$, non-negative retention, and strict mathematical reconciliation (<0.05 ct tolerance).
   - Synced German and English translation keys (`discount_margin_absorbed_label`, `discount_validation_warning`, `discount_validation_error`, `discount_adjusted_baseline_subtitle`).

3. **Default Timeframe in Tab 3 (Tagesrhythmus):**
   - Changed default timeframe from `all_time` to `last_30` (Letzte 30 Tage) so users immediately see current intraday rhythm.

4. **Mobile Responsiveness Optimization:**
   - Added responsive `@media (max-width: 768px)` stylesheet.
   - Mobile canvas padding tightened to `0.6rem` sides / `1.25rem` top to prevent wasted vertical screen space.
   - Smooth horizontal touch-scrollable tabs bar (`overflow-x: auto; flex-wrap: nowrap;`).
   - Mobile card scaling: Hero numbers scaled to `1.65rem` and paddings tightened for clean vertical stacking.
   - Dynamic chart resizing via `PLOT_CONFIG = {'displayModeBar': False, 'responsive': True}` across all 14 Plotly charts.
   - Responsive sidebar with `85vw` max width on small phones (e.g. iPhone SE).

5. **Tab Reordering & WIP Grouping:**
   - Promoted **12-Uhr-Regel Audit** to prominent Tab 2 position (right after Brent vs. Pump).
   - Moved experimental/in-progress features (**Tankberater** and **RAG**) to the very end of the tab bar with explicit `(in Arbeit)` / `(WIP)` designations.

6. **Granular Economic Price Decomposition Engine (`src/gasprice/price_decomposition.py`):**
   - Built mathematical decomposition engine breaking down gross pump prices into all 13 industrial and regulatory layers (Crude FOB, Crude Freight & Pipeline, Crack Spread, Tanklager & TKW Secondary Logistics, Dealer Commission, Payment Interchange Card Fees, Brand Net Profit, Energy Tax, CO2, EBV, VAT).
   - Mathematical reconciliation verified: sum of all components strictly equals gross pump price (<0.001 € tolerance).
   - Integrated into `ui/04_app.py` behind the scenes while keeping the outer visual display of the Price Tower 100% identical as requested.

7. **Tankberater Tab Deactivation & Lockdown:**
   - Disabled and grayed out the Tankberater tab (`pointer-events: none; opacity: 0.35; filter: grayscale(1); cursor: not-allowed`).
   - Labeled with `🔒 Tankberater (deaktiviert)` / `🔒 Tank Advisor (Disabled)`.
   - Disabled all child inputs, map, and sliders so nothing can be clicked or interacted with.

8. **Test Suite & Verification:**
   - All 86 pytest unit tests pass cleanly (`86 passed in 1.82s`).
   - Fully synced German (`de.json`) and English (`en.json`) translations.

---

### ⏳ Planned / What's Left for Today & Next

1. **Spam-sichere Suggestion- & Feedback-Box:**
   - Honeypot-Feld (unsichtbares Input-Feld, das Bots entlarvt).
   - Rate-Limiting (max. 1 Nachricht alle 5 Min. pro Session/IP).
   - Speicherung in lokaler SQLite/Parquet-Datei oder Weiterleitung via Discord/Telegram-Webhook (schützt private E-Mail vor Spam).

2. **Raffinerie- & Frachtkosten-Dekomposition:**
   - Großhandel/Crack-Spread im oberen Preisaufbau-Turm optional als eigene Schicht visualisieren.
   - Binnenschiff-Frachtkosten / Pegel Kaub Anbindung (Pegelonline API) zur Modellierung von Kleinwasserzuschlägen (KWZ) für Transporte nach Süddeutschland.

3. **Spatial Brand Analysis (Local Pricing Radius / Umkreisanalyse):**
   - Lokale Preisaufschläge relativ zu den nächsten 10–30 Nachbarstationen (z. B. 10 km Umkreis Niestetal / Kassel) zur Bereinigung von Autobahn- vs. Landstationen.

4. **Final Review:**
   - Überprüfung aller UI-Elemente und Metriken auf Konsistenz.

---

## Recent Changes
- Added **Tankrabatt 2 End (Jul 2026)** to the Event Study analysis (`ui/04_app.py`, translations), including legislative milestones, symmetric event study trajectories, auto-generated tax hike verdict, and unit tests.
- Added **Crude Oil Unit Display** selector to the dashboard sidebar, allowing users to toggle Brent crude prices between €/L, $/barrel (USD global benchmark), €/barrel (EUR European market), or both, with dynamic updates to KPI cards and chart hover tooltips.
- Ran incremental data pipeline updates extending historical fuel prices and macroeconomic/futures baselines through **September 2026**.
- Documented **Data & Pipeline Architecture** (`docs/architecture.md`) detailing Parquet vs. RDBMS selection, state carry-forward incremental processing, and geographic station-count weighting design.
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
- [x] Document pipeline architecture & storage design: `docs/architecture.md`
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

---

## Idea Backlog (Parked / Exploratory)

- **B2B Fuel Pricing Engine / Station Copilot (Parked):**
  - *Concept:* Build a real-time competitor tracking and dynamic pricing recommendation engine for independent / Mittelstand fuel stations, exploiting MTS-K low-latency feeds and enforcing mathematically zero § 3 KPAnG violations.
  - *Assessment (Unrealistic for now):* Requires official Bundeskartellamt MTS-K licensing (Tankerkönig free consumer API blocks commercial use), complex physical POS/pump hardware integration (IFSF protocol), and high sales friction convincing station owners without existing petroleum industry network. Parked to focus on consumer-facing and analytics-first ideas.

