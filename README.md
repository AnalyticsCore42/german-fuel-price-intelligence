# German Fuel Price Intelligence

An interactive analytics pipeline and premium dashboard analyzing retail margins, taxation, policy interventions (the 2022 and 2026 *Tankrabatt* fuel discounts), and spatial pricing dynamics across 14,000+ gasoline stations in Germany.

---

## Features
- **Taxes & Margins Engine:** Automatically calculates net prices, VAT, CO₂ pricing (including 2026 auction corridors), EBV contributions, and energy taxes.
- **Refined Product Spreads:** Tracks refinery vs. retail margins by blending futures data (RBOB, Ethanol, Heating Oil) to isolate actual retail profit margins.
- **Daily Rhythms:** Analyzes hourly pricing dynamics, highlighting the impact of the April 1, 2026 regulation restricting price hikes to once a day (12:00 PM).
- **Brand & Regional Comparisons:** Evaluates pricing deviations across major corporate groups, independent operators, and geographic zones (PLZ).
- **Smart Gas Station Finder (Upcoming):** Finds local stations and optimizes recommendations by factoring in vehicle consumption, tank size, and detour fuel costs.

---

## Directory Structure
- `ui/04_app.py` — Streamlit dashboard containing the analytical tabs.
- `start_dashboard.py` — Conveniency launcher script that automatically overrides headless settings to open the dashboard in your system's browser.
- `scripts/` — Vectorized data cleaning and daily aggregation ETL scripts.
- `docs/` — Ground-truth documentation including legislative policy timelines, corporate brand ownership trees, and RAG strategy details.
- `data/` — Storage folder for aggregated price statistics and macroeconomic baseline Parquet datasets.

---

## Getting Started

### 1. Installation
Clone the repository and install the dependencies:
```bash
pip install -r requirements.txt
```
*(Make sure `folium` and `streamlit-folium` are installed if you are using the Finder features).*

### 2. Launching the Dashboard
Start the dashboard locally:
```bash
python3 start_dashboard.py
```
This script will automatically open the UI in your default web browser on `http://localhost:8501`.

### 3. Running the Data Update Pipeline
To download the latest historical prices from Tankerkönig and update all dashboard metrics:
```bash
# 1. Update Brent Crude & EUR/USD macro baseline
python3 scripts/01_update_brent_crude.py

# 2. Update refined product baselines
python3 scripts/05_fetch_refined_product_baseline.py

# 3. Download daily price CSV logs (idempotent; skips existing)
python3 scripts/03_download_pump_prices.py

# 4. Clean stations metadata and map corporate/postcode boundaries
python3 scripts/01_clean_stations.py

# 5. Build consolidated dashboard datasets
python3 scripts/04_build_dashboard_dataset.py

# 6. Rebuild local statistics for the Gas Station Finder
python3 scripts/07_station_price_stats.py
```
