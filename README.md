# German Fuel Price Intelligence

[![GCP Cloud Run](https://img.shields.io/badge/Deployed%20on-GCP%20Cloud%20Run-blue?logo=google-cloud&logoColor=white)](https://gasoline-dashboard-glxitfsnbq-ey.a.run.app)
**Live Demo:** [gasoline-dashboard-glxitfsnbq-ey.a.run.app](https://gasoline-dashboard-glxitfsnbq-ey.a.run.app)

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
- `src/gasprice/` — Core Python package containing the ETL pipeline modules.
- `scripts/run_pipeline.py` — Central orchestrator that runs all pipeline steps sequentially.
- `scripts/exploratory/` — Diagnostic and exploratory analysis scripts.
- `ui/04_app.py` — Streamlit dashboard containing the analytical tabs.
- `ui/translations/` — Externalized i18n strings for the dashboard (`en.json`, `de.json`).
- `start_dashboard.py` — Convenience launcher script that automatically overrides headless settings to open the dashboard in your system's browser.
- `docs/` — Ground-truth documentation including legislative policy timelines, corporate brand ownership trees, and RAG strategy details.
- `data/` — Storage folder for aggregated price statistics and macroeconomic baseline Parquet datasets.

---

## Getting Started

### 1. Installation
Clone the repository and create a fresh virtual environment. **Never commit the `.venv/` folder** — it is already ignored and must be rebuilt locally on each machine/OS.

```bash
# 1. Clone
 git clone <your-repo-url>
 cd 1_Project_German_GasolinePrices21.05

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

## Next Steps
- **Cheapest Station Around Me:** Location-aware finder that ranks nearby stations by effective price including a short detour.
- **RAG Pipeline:** Natural-language Q&A over the dataset and documentation using a retrieval-augmented generation approach.
