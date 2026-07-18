# German Fuel Price Intelligence

[![GCP Cloud Run](https://img.shields.io/badge/Deployed%20on-GCP%20Cloud%20Run-blue?logo=google-cloud&logoColor=white)](https://gasoline-dashboard-751243983026.europe-west3.run.app)
**Live Demo:** [gasoline-dashboard-751243983026.europe-west3.run.app](https://gasoline-dashboard-751243983026.europe-west3.run.app)

An interactive analytics pipeline and premium dashboard analyzing retail margins, taxation, policy interventions (the 2022 and 2026 *Tankrabatt* fuel discounts), and spatial pricing dynamics across 14,000+ gasoline stations in Germany.

---

## Features
- **Taxes & Margins Engine:** Automatically calculates net prices, VAT, CO₂ pricing (including 2026 auction corridors), EBV contributions, and energy taxes.
- **Refined Product Spreads:** Tracks refinery vs. retail margins by blending futures data (RBOB, Ethanol, Heating Oil) to isolate actual retail profit margins.
- **Daily Rhythms:** Analyzes hourly pricing dynamics, highlighting the impact of the April 1, 2026 regulation restricting price hikes to once a day (12:00 PM).
- **Brand & Regional Comparisons:** Evaluates pricing deviations across major corporate groups, independent operators, and geographic zones (PLZ), including brand-level price-change frequency.
- **Tank Advisor:** Location-aware station recommender that ranks nearby stations by effective price including driving cost, vehicle consumption, tank size, and a detour estimate.

---

## Directory Structure
- `src/gasprice/` — Core Python package containing the ETL pipeline modules.
- `scripts/run_pipeline.py` — Central orchestrator that runs all pipeline steps sequentially.
- `scripts/exploratory/` — Diagnostic and exploratory analysis scripts.
- `ui/04_app.py` — Streamlit dashboard containing the analytical tabs.
- `ui/translations/` — Externalized i18n strings for the dashboard (`en.json`, `de.json`).
- `ui/tank_advisor_tab.py` — Tank Advisor tab implementation.
- `start_dashboard.py` — Convenience launcher script that automatically overrides headless settings to open the dashboard in your system's browser.
- `docs/` — Ground-truth documentation including legislative policy timelines, corporate brand ownership trees, RAG strategy details, the data dictionary, and pipeline architecture.
- `data/` — Storage folder for aggregated price statistics and macroeconomic baseline Parquet datasets.
- `tests/` — Unit tests for the pipeline, tax engine, and UI components.
- `LICENSE` — MIT license for the project code.

---

## Getting Started

### 1. Installation
Clone the repository and create a fresh virtual environment. **Never commit the `.venv/` folder** — it is already ignored and must be rebuilt locally on each machine/OS.

```bash
# 1. Clone
 git clone <your-repo-url>
 cd 3_German_Gasoline_Prices

# 2. Create virtual environment with Python 3.12
python3.12 -m venv .venv

# 3. Activate (Linux / macOS)
source .venv/bin/activate

# 3. Activate (Windows PowerShell)
# .venv\Scripts\Activate.ps1

# 4. Install dependencies
pip install -r requirements.txt
```

*(Make sure `folium` and `streamlit-folium` are installed if you are using the Finder features.)*

### 2. Launching the Dashboard
Start the dashboard locally:
```bash
python3 start_dashboard.py
```
This script will automatically open the UI in your default web browser on `http://localhost:8501` (or the next free port if 8501 is occupied).

### 3. Running the Data Update Pipeline
To download the latest historical prices from Tankerkönig and update all dashboard metrics, run the orchestrator:

```bash
python3 scripts/run_pipeline.py
```

This executes all steps in order:
1. Clean station metadata and map corporate/postcode boundaries
2. Update Brent Crude & EUR/USD macro baseline
3. Update refined product baselines
4. Build consolidated dashboard datasets
5. Rebuild local statistics for the Gas Station Finder

You can also run individual steps as modules, e.g.:
```bash
PYTHONPATH=src python3 -m gasprice.update_brent_crude
```

---

## Methodology & Key Decisions

### National Average Weighting
The dashboard national average is computed as a **station-count-weighted average** of the project's geographic regions, using the `station_count` field in `data/processed_regional_daily_margins.parquet`.

**Why:** An unweighted mean of station-hour observations over-represents regions with many small, volatile stations and under-represents stable, high-volume regions. Weighting by station count gives each region influence proportional to its share of the station network, producing a more representative national price. Empirical comparison showed the difference is usually small (~0.3 ct/L) but can exceed 5 ct/L on volatile days, especially since 2024. Population weighting was tested and produced nearly identical results because station counts correlate closely with population.

### Tank Advisor Cost Model
The Tank Advisor computes total cost for a full tank as:

```
total_cost = (station_price × tank_size) + (station_price × round_trip_km × consumption_l_per_100km / 100)
```

where `round_trip_km = 2 × 1.3 × straight_line_distance_km`. The 1.3× factor estimates actual road distance; doubling it accounts for the drive there and back. This prevents the model from over-recommending far-away stations that only look cheap because their driving cost is understated.

The advisor uses **point-in-time raw prices** (`data/tankerkoenig/prices/{YYYY}/{YYYY-MM-DD}.parquet`): for the user-selected date and time, it loads the last observation reported by each station up to that moment. This avoids the stale single-observation prices that were causing absurd recommendations like driving from Kassel to Hann. Münden for an imaginary €1.41/L E5 price.

The UI shows three reference stations — **recommended** (cheapest total cost), **closest**, and **most expensive** — plus a savings projection in €/month and €/year based on adjustable monthly driving distance.

Location input supports browser geolocation (`streamlit-js-eval`) and Photon (OpenStreetMap) address autocomplete with city names and postcodes.

### Data Quality
The pipeline now runs lightweight quality checks before writing daily outputs: date-gap detection, low-reporting-hour warnings, single-day price-jump outliers (>30 ct/L), and brand-level change-frequency sanity checks. These are logged as warnings rather than hard failures so a single noisy day does not block incremental updates.

---

## Data Sources & Licensing

- **Fuel price & station data:** [Tankerkönig](https://www.tankerkoenig.de) historical price archive, provided under the **CC BY-NC-SA 4.0** license (non-commercial use with attribution). The raw per-day files are not committed to this repository; only aggregated dashboard datasets are tracked.
- **Macroeconomic baselines:** Brent crude, EUR/USD, RBOB gasoline, heating oil, and ethanol futures data from [Yahoo Finance](https://finance.yahoo.com) for research and non-commercial analysis.

The source code in this repository is released under the **MIT License** (see `LICENSE`). The aggregated fuel-price outputs remain subject to the underlying Tankerkönig non-commercial terms.

---

## Next Steps
- **RAG Pipeline:** Natural-language Q&A over the dataset and documentation using a retrieval-augmented generation approach.
- **ML Forecasting:** Use station-level or regional features to predict short-term price movements and pass-through effects.
