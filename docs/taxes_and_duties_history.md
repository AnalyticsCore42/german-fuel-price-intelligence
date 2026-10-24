# Documentation: Taxes and Duties on Motor Fuels (Petrol & Diesel) in Germany
**Status:** May 2026 | **History:** 2003 – 2026 | **Future:** Approved changes from 2027

This document contains the exact legal tax rates, duties, and formulas strictly required to calculate the net product margin (refinery/distribution margin). All values are **net values** (before Value Added Tax), as VAT is always applied to the sum of the product price and all duties listed here.

---

## 1. Energy Tax (*Energiesteuer*, formerly *Mineralölsteuer*)
The Energy Tax is a fixed amount per liter of fuel.

**Current Situation (May 2026):**
Due to the current fuel discount (*Tankrabatt*, May 1, 2026 – June 30, 2026), the rates have been temporarily reduced.
*   **Petrol / Gasoline (*Benzin, Super E5/E10*):** 51.41 cents / liter
*   **Diesel (*Diesel*):** 33.00 cents / liter

**Historical Development:**
*   **Since 2003/2004 – Standard rate (*Regelsatz*):** Petrol: 65.45 ct/l | Diesel: 47.04 ct/l  
  *(The current standard rates have been in place since the end of the German “Ökosteuer” reform phase; petrol reached 65.45 ct/l in 2003 and diesel reached 47.04 ct/l in 2004.)*
*   **01.01.2019 – 31.05.2022:** Standard rate (*Regelsatz*) (Petrol: 65.45 ct/l | Diesel: 47.04 ct/l)
*   **01.06.2022 – 31.08.2022 (1st Fuel Discount / *1. Tankrabatt*):** Cut to EU minimum (Petrol: 35.90 ct/l | Diesel: 33.00 ct/l)
*   **01.09.2022 – 30.04.2026:** Standard rate (Petrol: 65.45 ct/l | Diesel: 47.04 ct/l)
*   **01.05.2026 – 30.06.2026 (2nd Fuel Discount / *2. Tankrabatt*):** Petrol: 51.41 ct/l | Diesel: 33.00 ct/l
*   **01.07.2026 – 30.09.2026:** Standard rate (Petrol: 65.45 ct/l | Diesel: 47.04 ct/l)
*   **01.10.2026 – 31.12.2026 (3rd Fuel Discount / *3. Tankrabatt*):** Petrol: 51.41 ct/l | Diesel: 33.00 ct/l

**Future (already approved):**
*   **From 01.01.2027:** Legal return to the standard rate (Petrol: 65.45 ct/l | Diesel: 47.04 ct/l).

---

## 2. CO₂ Price (*CO₂-Preis* under the *Brennstoffemissionshandelsgesetz - BEHG*)
The National Emissions Trading System (*Nationales Emissionshandelssystem - nEHS*) prices CO₂ emissions per metric ton (t). To calculate the price per liter of fuel, fixed, legally standardized emission factors (*Emissionsfaktoren*) are used.

**Calculation Formula:**
`CO₂ Surcharge (Euro/Liter) = (CO₂ Price per ton / 1000) * Emission Factor`

**Fixed Emission Factors:**
*   **Petrol (*Benzin*):** 2.38 kg CO₂ / liter
*   **Diesel (*Diesel*):** 2.65 kg CO₂ / liter

**Historical Development (Fixed Prices / *Festpreise* 2021–2025):**
*   **Up to 2020:** 0.00 € / t
*   **2021:** 25.00 € / t (➔ Petrol: 5.95 ct/l | Diesel: 6.63 ct/l)
*   **2022 & 2023:** 30.00 € / t (➔ Petrol: 7.14 ct/l | Diesel: 7.95 ct/l)
*   **2024:** 45.00 € / t (➔ Petrol: 10.71 ct/l | Diesel: 11.93 ct/l)
*   **2025:** 55.00 € / t (➔ Petrol: 13.09 ct/l | Diesel: 14.58 ct/l)

**Current Situation (2026): Auction Corridor (*Auktionskorridor*)**
Since January 1, 2026, there is no fixed price. Certificates are auctioned on the exchange (EEX Leipzig). The law mandates a corridor from **55 € (Minimum)** to **65 € (Maximum)**. There is also a **post-purchase fixed price (*Nachkauf-Festpreis*) of 68 €** if auction certificates run out.

Since oil companies usually price in risks at the pump in advance, we use three fixed scenarios for data analysis:
*   **Scenario A (Minimum - 55 €/t):** Petrol: 13.09 ct/l | Diesel: 14.58 ct/l
*   **Scenario B (Maximum - 65 €/t):** Petrol: 15.47 ct/l | Diesel: 17.23 ct/l *(Recommended baseline for margin analysis)*
*   **Scenario C (Post-purchase - 68 €/t):** Petrol: 16.18 ct/l | Diesel: 18.02 ct/l

---

## 3. EBV Contribution (*EBV-Beitrag* / *Erdölbevorratungsverband*)
This contribution finances Germany's strategic crisis reserve (90-day reserve / *Strategische Reserve*). It is extremely stable and has **not** changed over the last 7 years.

**Current Situation & History (unchanged since April 2012):**
*   **Petrol (*Benzin*):** exactly 0.27 cents / liter
*   **Diesel (*Diesel*):** exactly 0.30 cents / liter

---

## 4. Value Added Tax - VAT (*Mehrwertsteuer - MwSt.* / *Umsatzsteuer - USt.*)
VAT is applied **to the final price** (Net Product Price + Energy Tax + CO₂ Price + EBV Contribution). 

**History & Current Situation:**
*   **01.01.2019 – 30.06.2020:** 19 %
*   **01.07.2020 – 31.12.2020:** 16 % *(Temporary cut due to COVID-19 stimulus / Corona-Konjunkturpaket)*
*   **Since 01.01.2021 continuously to date (May 2026):** 19 %

---

## 5. Matrix for Data Engineering (ETL)
Summary table for mapping duties based on the `Timestamp`. For 2026, the recommended "Scenario B" (Maximum value 65 €) is assumed as the baseline for the CO₂ price.

| Period | Petrol Energy Tax (*EnergieSt.*) | Diesel Energy Tax (*EnergieSt.*) | CO₂ Price (t) | CO₂ Petrol (ct/l) | CO₂ Diesel (ct/l) | VAT (*MwSt.*) | Note / Event |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **2013–2018** | 65.45 ct/l | 47.04 ct/l | 0 € | 0.00 ct/l | 0.00 ct/l | 19 % | Stable rates; no CO₂ pricing |
| **2019 (Jan-Dec)** | 65.45 ct/l | 47.04 ct/l | 0 € | 0.00 ct/l | 0.00 ct/l | 19 % | - |
| **2020 (Jan-Jun)** | 65.45 ct/l | 47.04 ct/l | 0 € | 0.00 ct/l | 0.00 ct/l | 19 % | - |
| **2020 (Jul-Dec)** | 65.45 ct/l | 47.04 ct/l | 0 € | 0.00 ct/l | 0.00 ct/l | 16 % | VAT cut (COVID) |
| **2021 (Jan-Dec)** | 65.45 ct/l | 47.04 ct/l | 25 € | 5.95 ct/l | 6.63 ct/l | 19 % | BEHG introduced |
| **2022 (Jan-May)** | 65.45 ct/l | 47.04 ct/l | 30 € | 7.14 ct/l | 7.95 ct/l | 19 % | BEHG increase |
| **2022 (Jun-Aug)** | 35.90 ct/l | 33.00 ct/l | 30 € | 7.14 ct/l | 7.95 ct/l | 19 % | 1st Fuel Discount (*1. Tankrabatt*) |
| **2022 (Sep-Dec)** | 65.45 ct/l | 47.04 ct/l | 30 € | 7.14 ct/l | 7.95 ct/l | 19 % | End 1st Fuel Discount |
| **2023 (Jan-Dec)** | 65.45 ct/l | 47.04 ct/l | 30 € | 7.14 ct/l | 7.95 ct/l | 19 % | CO₂ increase paused |
| **2024 (Jan-Dec)** | 65.45 ct/l | 47.04 ct/l | 45 € | 10.71 ct/l | 11.93 ct/l | 19 % | BEHG increase |
| **2025 (Jan-Dec)** | 65.45 ct/l | 47.04 ct/l | 55 € | 13.09 ct/l | 14.58 ct/l | 19 % | BEHG increase |
| **2026 (Jan-Apr)** | 65.45 ct/l | 47.04 ct/l | 65 €* | 15.47 ct/l | 17.23 ct/l | 19 % | Auction corridor starts (*Scen. B) |
| **2026 (May-Jun)** | 51.41 ct/l | 33.00 ct/l | 65 €* | 15.47 ct/l | 17.23 ct/l | 19 % | 2nd Fuel Discount (*2. Tankrabatt*) |
| **2026 (Jul-Sep)** | 65.45 ct/l | 47.04 ct/l | 65 €* | 15.47 ct/l | 17.23 ct/l | 19 % | Return to standard rate |
| **2026 (Oct-Dec)** | 51.41 ct/l | 33.00 ct/l | 65 €* | 15.47 ct/l | 17.23 ct/l | 19 % | 3rd Fuel Discount (*3. Tankrabatt*) |
| **from Jan 2027** | 65.45 ct/l | 47.04 ct/l | 65 €* | 15.47 ct/l | 17.23 ct/l | 19 % | Return to standard rate |

*(Note for calculating total duties: The EBV contribution / EBV-Beitrag of 0.27 ct/l for petrol and 0.30 ct/l for diesel must be added consistently across all rows.)*
