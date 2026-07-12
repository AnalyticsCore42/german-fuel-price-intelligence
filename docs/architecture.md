# Pipeline & Data Architecture

This document details the architectural decisions, data processing optimizations, and design choices of the German Fuel Price Intelligence project.

---

## 1. Data Storage: Why Parquet Instead of a Relational Database?

The project stores all historical raw prices and aggregated metrics in the Apache Parquet format rather than in a traditional relational database (such as PostgreSQL or SQLite). This design offers several advantages for analytical workloads:

### A. Columnar Storage (OLAP vs. OLTP)
*   **Traditional Databases (Row-Oriented / OLTP):** Structured to insert and update individual rows quickly (ideal for transactional systems like web shops). However, calculating a daily average price requires reading the entire row including unused columns (station UUIDs, local street names, and coordinates), causing significant I/O overhead.
*   **Parquet (Columnar / OLAP):** Stores each column's data contiguously on disk. To compute the daily average for E5 petrol, the query engine reads only the `date` and `price_e5` columns, completely skipping the rest of the data.

### B. High Compression Ratios
*   Because data in a column is homogeneous (e.g., millions of `Float64` price values stored sequentially), compression algorithms like **ZSTD** (used in this project) can achieve extremely high compression ratios. A single column of prices contains many identical or close values, which compress far better than a row containing a mix of text, dates, and numbers.
*   The historical dataset spanning 2021 to 2026 comprises over 600 million station-hour records. Uncompressed, this would exceed 30 GB. Stored as compressed Parquet, it is reduced to a fraction of that size, allowing fast loads even on standard laptops.

### C. Direct Integration with Polars
*   The `polars` library features native C++ readers for Parquet. It optimizes queries automatically using:
    *   **Projection Pushdown:** Only loading columns requested by the code.
    *   **Predicate Pushdown:** Reading only the metadata to skip entire row groups that do not match the date filters (e.g., reading only 2022 data without parsing the rest of the file).

### D. Zero Infrastructure & Serverless Portability
*   Traditional databases require a running database server, which introduces overhead in maintenance, credentials, connection pooling, and hosting costs.
*   Parquet files are simple flat files. They can be stored locally, committed to Git (for small aggregates), or placed in a cloud bucket (like Google Cloud Storage). The application can run locally, in a Kaggle notebook, or on GCP Cloud Run without configuring database connections.

---

## 2. ETL Optimization: Incremental Processing

Running the entire data pipeline from scratch on 5+ years of raw price logs (10+ GB) for a daily update is impractical. The pipeline is designed to be fully incremental:

```
[New Daily Price Parquet] ─> [build_hourly_snapshot()]
                                   ▲
                                   │ (Hour 0 Seeded)
                     [station_carry_forward_state.parquet]
                                   │
                                   ▼
                     [Deduplicated & Appended to Outputs]
```

### A. Idempotent Downloader (`download_pump_prices.py`)
*   Uses a manifest file (`data/tankerkoenig/prices/.download_manifest.json`) containing SHA-256 hashes of all completed files.
*   During daily runs, it skips previously downloaded historical files, fetching only the new daily CSV and converting it to Parquet on the fly.
*   It re-downloads the last 7 days of data to catch late corrections or backfilled observations from the source.

### B. State Carry-Forward ETL (`build_dashboard_dataset.py`)
*   To build daily averages, the pipeline needs a continuous 24-hour grid for every station. Instead of reading all history to find the last price, it loads the previous day's end-of-day state from `station_carry_forward_state.parquet` (storing station prices at 23:00).
*   It uses this state to seed Hour 0 for the new day, forward-fills the day's price changes, and then appends the new daily averages to the historical output parquets (`processed_daily_margins.parquet`, etc.).
*   A daily update takes only a few seconds.

---

## 3. Geographic Weighting Design

To calculate a representative national average price, the dashboard uses a **station-count-weighted** aggregation based on 10 geographic regions rather than a simple average of all price updates.

### A. Defining the Regions
Stations are mapped to regions using the first digit of their German postcode (PLZ):
*   **0:** East (Saxony/Thuringia/S.Brandenburg)
*   **1:** Northeast (Berlin/Brandenburg/Mecklenburg)
*   **2:** North (Hamburg/Schleswig-Holstein/Bremen/N.Lower Saxony)
*   **3:** Central (Hesse/C.Lower Saxony/W.Thuringia/E.Westphalia)
*   **4:** West (W.Westphalia/W.Lower Saxony)
*   **5:** West-Central (S.Westphalia/Rhineland-Palatinate/Saarland)
*   **6:** Southwest (S.Hesse/Rhineland-Palatinate/N.Baden-Württemberg)
*   **7:** Southwest (S.Baden-Württemberg)
*   **8:** South (S.Bavaria/SE.Baden-Württemberg)
*   **9:** Southeast (N.Bavaria/S.Thuringia)

### B. Mitigating Reporting Frequency Bias
*   **Urban Stations:** Highly competitive urban stations change prices frequently (often 10–15 times a day), creating many rows in the raw log.
*   **Rural Stations:** Stations in rural areas with less local competition change prices less frequently (1–3 times a day).
*   **The Bias:** A simple average of all raw price observations would be heavily skewed towards urban prices because urban stations report far more frequently.
*   **The Solution:** The pipeline first aggregates prices to a daily average per region, and then weights those regional averages by the total physical station count of each region:
    
    $$\text{Price}_{\text{national}} = \frac{\sum (\text{Price}_{\text{region}} \times \text{StationCount}_{\text{region}})}{\sum \text{StationCount}_{\text{region}}}$$

This weighting ensures that less volatile rural areas contribute fairly to the national average, producing a more representative price index.
