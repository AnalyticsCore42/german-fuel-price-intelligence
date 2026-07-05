# Data Dictionary

This document describes the structured Parquet datasets produced and consumed by the German fuel price pipeline. All prices are in **EUR per liter** unless otherwise noted.

---

## Dashboard datasets

These files are read directly by `ui/04_app.py`.

### `processed_daily_margins.parquet`
National daily averages and margin decomposition. **Loaded by:** `load_data()`.

| Column | Type | Description |
| --- | --- | --- |
| `date` | Date | Calendar date (2021-01-01 onward). |
| `price_diesel` | Float64 | National average diesel pump price. Since 2026-07-04 this is station-count-weighted via the regional file. |
| `price_e5` | Float64 | National average E5 pump price. Station-count-weighted. |
| `price_e10` | Float64 | National average E10 pump price. Station-count-weighted. |
| `stations_reporting` | UInt32 | Max number of stations reporting in any hour of the day. |
| `Raw_Material_EUR_per_Liter` | Float64 | Raw material cost per liter (Brent crude converted to EUR/L). |
| `brent_eur_liter` | Float64 | Same as above; kept for backward compatibility. |
| `e5_product_eur_liter` | Float64 | Estimated refined E5 product price (RBOB + ethanol blend, EUR/L). |
| `e10_product_eur_liter` | Float64 | Estimated refined E10 product price. |
| `diesel_product_eur_liter` | Float64 | Estimated refined diesel product price. |
| `{fuel}_vat` | Float64 | Value-added tax component for the fuel. |
| `{fuel}_ebv` | Float64 | EBV (stockholding association) levy. |
| `{fuel}_co2` | Float64 | CO₂ pricing component. |
| `{fuel}_energy` | Float64 | Energy tax component. |
| `{fuel}_net_price` | Float64 | Pump price minus VAT: product + duties + CO₂ + EBV. |
| `margin_{fuel}` | Float64 | Net product spread: `net_price - Raw_Material_EUR_per_Liter`. |
| `retail_margin_{fuel}` | Float64 | Retail/refining spread over refined product: `net_price - {fuel}_product_eur_liter`. |
| `refining_spread_{fuel}` | Float64 | Refining spread: `{fuel}_product_eur_liter - Raw_Material_EUR_per_Liter`. |

### `processed_intraday.parquet`
Hourly national price patterns. **Loaded by:** Daily Rhythm tab.

| Column | Type | Description |
| --- | --- | --- |
| `date` | Date | Calendar date. |
| `hour` | Int | Hour of day in Europe/Berlin local time (0-23). |
| `price_diesel` | Float64 | Mean diesel price across reporting stations for that hour. |
| `price_e5` | Float64 | Mean E5 price for that hour. |
| `price_e10` | Float64 | Mean E10 price for that hour. |
| `stations_reporting` | UInt32 | Number of stations that reported a price in that hour. |

### `processed_brand_daily_margins.parquet`
Daily margins and price-change frequency by brand or owner. **Loaded by:** Brand Comparison tab.

| Column | Type | Description |
| --- | --- | --- |
| `date` | Date | Calendar date. |
| `analysis_level` | String | `"brand"` (visible brand bucket) or `"owner"` (corporate group). |
| `comparison_group` | String | Brand or owner name. Small brands are grouped into `Other brands (<50 stations)`. |
| `price_{fuel}` | Float64 | Average pump price for the group. |
| `stations_reporting` | UInt32 | Stations in the group that reported a price that day. |
| `station_count` | UInt32 | Total stations in the group (from metadata). |
| `changes_{fuel}` | Float64 | Mean number of true price transitions per station in the group that day. |
| All margin / tax / product columns | Float64 | Same decomposition as `processed_daily_margins.parquet`. |

### `processed_regional_daily_margins.parquet`
Daily margins by geographic region. **Loaded by:** Regional Pricing tab and used to compute the station-count-weighted national average.

| Column | Type | Description |
| --- | --- | --- |
| `date` | Date | Calendar date. |
| `region` | String | Geographic region label (e.g. `North (Hamburg/Schleswig-Holstein/Bremen/N.Lower Saxony)`). |
| `price_{fuel}` | Float64 | Average pump price in the region. |
| `stations_reporting` | UInt32 | Stations in the region that reported that day. |
| `station_count` | UInt32 | Total stations in the region (from metadata). |
| All margin / tax / product columns | Float64 | Same decomposition as `processed_daily_margins.parquet`. |

---

## Pipeline internal datasets

### `station_carry_forward_state.parquet`
Last known price per station, used to seed hour 0 on the next incremental run.

| Column | Type | Description |
| --- | --- | --- |
| `station_uuid` | String | Tankerkönig station UUID. |
| `price_diesel` | Float64 | Last observed diesel price. |
| `price_e5` | Float64 | Last observed E5 price. |
| `price_e10` | Float64 | Last observed E10 price. |

### `station_price_stats.parquet`
Long-run averages and latest prices per station for the Tank Advisor.

| Column | Type | Description |
| --- | --- | --- |
| `station_uuid` | String | Tankerkönig station UUID. |
| `station_name` | String | Station name. |
| `brand` | String | Visible brand. |
| `city`, `street`, `house_number`, `post_code` | String | Address fields. |
| `latitude`, `longitude` | Float64 | WGS84 coordinates. |
| `avg_price_{fuel}` | Float64 | Long-run average price across the available history. |
| `latest_price_{fuel}` | Float64 | Most recent observed price. |
| `latest_price_date` | Date | Date of the latest observation. |

---

## Macro / baseline datasets

### `processed_macro_baseline.parquet`
Daily Brent crude and EUR/USD macro baseline.

| Column | Type | Description |
| --- | --- | --- |
| `date` | Date | Calendar date. |
| `DCOILBRENTEU` | Float64 | Brent crude USD per barrel (EIA ticker). |
| `DEXUSEU` | Float64 | EUR/USD exchange rate (ECB ticker). |
| `Raw_Material_EUR_per_Liter` | Float64 | Brent converted to EUR per liter of raw material. |

### `processed_refined_product_baseline.parquet`
Daily refined product baseline from futures.

| Column | Type | Description |
| --- | --- | --- |
| `date` | Date | Calendar date. |
| `eur_usd` | Float64 | EUR/USD rate used for conversion. |
| `brent_usd_barrel` | Float64 | Brent USD/barrel. |
| `brent_eur_liter` | Float64 | Brent EUR/liter. |
| `gasoline_base_eur_liter` | Float64 | RBOB gasoline futures converted to EUR/L. |
| `diesel_base_eur_liter` | Float64 | Heating oil futures (diesel proxy) converted to EUR/L. |
| `ethanol_base_eur_liter` | Float64 | Ethanol futures converted to EUR/L. |
| `e5_product_eur_liter` | Float64 | Blended E5 product estimate. |
| `e10_product_eur_liter` | Float64 | Blended E10 product estimate. |
| `diesel_product_eur_liter` | Float64 | Blended diesel product estimate. |

---

## Notes

- `{fuel}` is a placeholder for `e5`, `e10`, or `diesel`.
- Net prices and all margin columns are **before VAT** because VAT is levied on the final pump price, not on the product cost.
- The national average pump prices in `processed_daily_margins.parquet` are computed on the fly in `ui/04_app.py` as a station-count-weighted average of `processed_regional_daily_margins.parquet`. The parquet itself still stores the original unweighted values for backward compatibility; the dashboard reweights them at load time.
