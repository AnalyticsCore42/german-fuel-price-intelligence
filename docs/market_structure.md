# German Fuel Brand And Ownership Ground Truth

This file includes the working mapping from visible German fuel-station brand names to ownership groups, the dashboard grouping rules, and the market-context notes needed for brand-level margin analysis.

## How This File Is Used

- `src/gasprice/clean_stations.py` cleans raw station brands to uppercase names and assigns `corporate_group`.
- `src/gasprice/build_dashboard_dataset.py` creates two dashboard comparison levels:
  - `brand`: visible brand names, with all brands below 50 stations grouped as `Other brands (<50 stations)`.
  - `owner`: corporate ownership groups from `corporate_group`.
- `ui/04_app.py` uses those two levels in the Brand Comparison tab.
- The future RAG pipeline should read this file as the source of truth for brand and ownership interpretation instead of guessing ownership dynamically.

## Dashboard Grouping Rules

The dashboard intentionally separates customer-facing brand behavior from ownership-level behavior.

- Brand comparison: each visible brand with at least 50 stations stays separate, while smaller brands are grouped into `Other brands (<50 stations)`.
- Ownership comparison: brands owned or operated together are grouped under one `corporate_group`.
- Unknown or unmapped raw brands are not forced into a major group; they stay in `Unknown` or `Independent / Small Operator`.

This structure lets the analysis compare, for example, whether a cheaper child brand behaves differently from a premium brand under the same owner.

## Exact ETL Mapping

| Raw brand value | Corporate group |
| --- | --- |
| ACCESS | Couche-Tard (Total) |
| AGIP | Eni |
| AGIP ENI | Eni |
| ARAL | BP (Aral) |
| AVIA | AVIA Cooperative |
| BAYWA | Agricultural Co-ops (Raiffeisen/BayWa) |
| BFT | BFT (Independent Assoc.) |
| BFT (FREIE) | BFT (Independent Assoc.) |
| CALPAM | Bolloré Group |
| CLASSIC | Christian Lühmann GmbH |
| ED | Erich Doetsch (ED) |
| ELAN | Couche-Tard (Total) |
| ESSO | EG Group (Esso) |
| FREI | BFT (Independent Assoc.) |
| FREIE | BFT (Independent Assoc.) |
| GULF | Gulf / Independent |
| HEM | Oilinvest (HEM/Tamoil) |
| HOYER | Hoyer Group |
| JET | Stonepeak (JET) |
| MARKANT | Westfalen AG |
| NORDOEL | Lother GmbH |
| OIL! | Prax Group |
| ORLEN | Orlen (Polish State) |
| PM | PM Pfennings |
| Q1 | Q1 Energie AG |
| RAIFFEISEN | Agricultural Co-ops (Raiffeisen/BayWa) |
| SB | SB (Generic/Discount) |
| SCORE | SCORE GmbH |
| SHELL | Shell |
| SPRINT | Hoyer Group |
| STAR | Orlen (Polish State) |
| SUPERMARKT | Grocery Retailers |
| T | Oilinvest (HEM/Tamoil) |
| TANKCENTER | Grocery Retailers |
| TEAM | team energie GmbH |
| TOTAL | Couche-Tard (Total) |
| TOTALENERGIES | Couche-Tard (Total) |
| UNKNOWN | Unknown |
| WESTFALEN | Westfalen AG |
| Any unmapped brand | Independent / Small Operator |

## Tier 1: Global Conglomerates And Big Oil

These are large multinational players with more centralized pricing structures.

- BP (British Petroleum)
  - Brands: ARAL
  - Context: BP operates in Germany almost entirely under the Aral brand. Aral is treated as the German-facing BP retail brand.
- Alimentation Couche-Tard / Circle K
  - Brands: TOTALENERGIES, TOTAL, ELAN, ACCESS
  - Context: Couche-Tard acquired the German TotalEnergies retail network in early 2024. TotalEnergies is treated as the premium-facing brand, while Elan and Access are discount or secondary partner brands.
- Shell plc
  - Brands: SHELL
  - Context: Shell operates directly under its global brand.
- Eni S.p.A.
  - Brands: AGIP ENI, AGIP
  - Context: Agip/Eni is tracked separately from generic `SB` signs. Some SB stations may be connected to Eni in practice, but the data cannot isolate that cleanly.
- PKN Orlen
  - Brands: STAR, ORLEN
  - Context: Orlen controls the Star/Orlen network. Star is the legacy German-facing brand, while Orlen is the active rebrand direction.

## Tier 2: Private Equity And Recent Acquisitions

These networks recently changed hands, so older ownership assumptions can be misleading.

- Stonepeak and EEP
  - Brands: JET
  - Context: Stonepeak and EEP closed a EUR 2.5 billion deal on December 1, 2025, to acquire JET from Phillips 66, with Phillips 66 retaining a 35% non-operative stake. JET is treated as an aggressive discount brand among the major networks.
- EG Group
  - Brands: ESSO
  - Context: ExxonMobil owns the Esso brand and supplies fuel, while EG Group operates the physical station network and sets retail pricing.
- Prax Group
  - Brands: OIL!
  - Context: Prax fully acquired OIL! from the German Mabanaft group.

## Tier 3: Mittelstand Consolidations

These are large German or regional operators that can otherwise look like unrelated independent brands.

- Wilhelm Hoyer Group
  - Brands: HOYER, SPRINT
  - Context: Hoyer is a large independent northern German player. Combining Hoyer and Sprint creates one corporate block.
- Westfalen AG
  - Brands: WESTFALEN, MARKANT
  - Context: Westfalen is the premium brand. Markant, acquired from Kuwait Petroleum in 2006, functions as a discount or secondary arm.
- Christian Lühmann GmbH
  - Brands: CLASSIC
  - Context: Classic is treated as an independent family-owned network, not as part of Mabanaft.
- Lother GmbH
  - Brands: NORDOEL
  - Context: Nordoel is a regional powerhouse, especially around Schleswig-Holstein and northern Germany.
- Q1 Energie AG
  - Brands: Q1
  - Context: Q1 broke away from the AVIA cooperative in the 1980s and is treated as its own independent competitor.
- team energie GmbH
  - Brands: TEAM
  - Context: Team is tracked as its own mid-sized operator.
- PM Pfennings
  - Brands: PM
  - Context: PM is tracked as its own operator.
- SCORE GmbH
  - Brands: SCORE
  - Context: Score is tracked as its own operator.
- Erich Doetsch
  - Brands: ED
  - Context: ED is tracked as its own operator.

## Tier 4: International Niche Holdings

- Oilinvest Group
  - Brands: HEM, T
  - Context: HEM and T/Tamoil belong to the Oilinvest downstream retail structure.
- Bolloré Group
  - Brands: CALPAM
  - Context: Calpam retail stations are treated as owned by the French Bollore Group and should not be confused with similarly named Hamburg bunkering activity.
- Gulf / Independent
  - Brands: GULF
  - Context: Gulf is kept as its own independent/niche label because ownership and operation can be locally fragmented.

## Tier 5: Cooperatives, Associations, Generics, And Fragmented Pricing

These groups should not be interpreted as centrally priced in the same way as large corporate chains.

- AVIA Cooperative
  - Brands: AVIA
  - Context: AVIA is an umbrella cooperative. A price movement at one AVIA station does not necessarily imply the same pricing decision at another AVIA station.
- BFT Independent Association
  - Brands: BFT (FREIE), BFT, FREI, FREIE
  - Context: These labels represent independent or association-linked operators. Treat them as fragmented rather than centrally controlled.
- Agricultural co-ops
  - Brands: RAIFFEISEN, BAYWA
  - Context: These are agricultural cooperative or cooperative-adjacent networks.
- Grocery retailers
  - Brands: SUPERMARKT, TANKCENTER
  - Context: These are typically supermarket or retail-center fuel stations and may behave differently from highway or full-service branded networks.
- SB generic discount
  - Brands: SB
  - Context: SB means self-service and is ambiguous. Eni uses the label heavily, but independent operators also use it, so the dashboard keeps SB isolated.
- Unknown
  - Brands: UNKNOWN
  - Context: Missing or empty raw brand values are normalized to `UNKNOWN` and mapped to `Unknown`.
- Independent / Small Operator
  - Brands: any raw brand not listed in the mapping table
  - Context: Unmapped brands remain in the long-tail independent bucket instead of being guessed into a larger group.

## Premium And Discount Child-Brand Pairs To Watch

- Couche-Tard: compare TOTALENERGIES/TOTAL against ELAN and ACCESS.
- Westfalen AG: compare WESTFALEN against MARKANT.
- Hoyer Group: compare HOYER against SPRINT.
- Orlen: compare STAR against ORLEN during the rebrand period.
- Oilinvest: compare HEM against T/Tamoil where both appear.
- Cooperatives and associations: compare AVIA, BFT/FREIE, RAIFFEISEN, and BAYWA carefully because centralized control is weaker.

## Related 2026 Policy Context: The 12:00 PM Rule

The Kraftstoffpreisanpassungsgesetz (KPAnG), enacted on April 1, 2026, restricts retail fuel stations in Germany to raising prices only once per calendar day, strictly between 11:55 and 12:05 PM (with an operational/forensic buffer up to 13:00). Price decreases remain legally unrestricted at all times.

Empirical analysis across 14,687 stations with cross-brand competitors within 2.5 km and over 5.4 million price reaction events reveals profound shifts in market microstructure, algorithmic sequencing, and compliance behavior.

---

## Empirical Market Dynamics: Pre- vs. Post-12:00 Rule

### 1. Collapse of Intraday Price Churn (-64.5%)
- **Pre-Rule (Q1 2026, Free Market):** 4,011,454 leader-follower reaction events across 4 sample days. Stations engaged in 5 to 8 daily price cycles (morning rush, midday spike, afternoon lull, evening commute surge, late night spike).
- **Post-Rule (Q2 2026, Statutory Rule):** 1,425,295 leader-follower reaction events across 4 sample days. Compressing all daily price increases into a single 12:00 PM window eliminated 64.5% of intraday pricing churn.

### 2. Market Leadership Inversion (Aral Dethroned by Discounters)
In competition economics, the **Leadership Ratio** measures how frequently a brand initiates an intraday price move before its local neighbors react:

$$\text{Leadership Ratio} = \frac{\text{Lead Events}}{\text{Lead Events} + \text{Follow Events}}$$

| Corporate Group / Brand | Q1 2026 Leadership (Pre-Rule) | Q2 2026 Leadership (Post-Rule) | Strategic Shift |
| :--- | :--- | :--- | :--- |
| **Stonepeak (JET)** | 52.1% | **52.8%** | **New Market Leader (+0.7%)** |
| **Oilinvest (HEM / Tamoil)** | 52.0% | **51.8%** | Co-Leader |
| **BFT (Independent Assoc.)** | 48.3% | **51.2%** | **Became Leader (+2.9%)** |
| **Shell** | 48.8% | 49.7% | Reactive Matcher (+0.9%) |
| **BP (Aral)** | **53.0% (Former Leader)** | **49.6%** | **Lost Leadership (-3.4%)** |
| **EG Group (Esso)** | 50.4% | 48.4% | Trailing (-2.0%) |
| **Independent / Small Operators** | 46.8% | 49.7% | Aggressive Follower (+2.9%) |
| **Couche-Tard (Total)** | 46.7% | 44.2% | Passive Follower (-2.5%) |

**Economic Driver of the Inversion:**
Prior to April 2026, BP (Aral) led the market by initiating nationwide price-increase waves. Under the 12:00 rule, price increases are restricted to noon. The competitive arena shifted entirely to the **afternoon price-cutting race (13:00–20:00)**. Because downward moves are legally unlimited, discounters like **JET (52.8%)**, **HEM (51.8%)**, and **BFT (51.2%)** take the initiative, aggressively dropping prices to siphon commuter volume. Aral and Shell were forced into a reactive follower role, trailing behind discounters' price cuts by ~19 to 22 minutes.

---

## Algorithmic Sequencing at 12:00 PM (Noon Window)

Analysis of 43,877 price hikes between 12:00 and 12:15 PM reveals microsecond-level synchronization across major corporate networks:

| Corporate Group / Brand | Total Noon Hikes | Hikes at 12:00 | Hikes at 12:01 | Hikes at 12:02 | Share First 3 Mins | Avg Minute of Hike |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Shell** | 5,125 | **1,464** | **3,661** | 0 | **100.0%** | **12:00.7** (First Mover) |
| **BP (Aral)** | 7,204 | 2 | **7,202** | 0 | **100.0%** | **12:01.0** (Synchronized Push) |
| **AVIA Cooperative** | 1,855 | 594 | 761 | 318 | **90.2%** | **12:01.4** |
| **Stonepeak (JET)** | 2,267 | **0** | **0** | **1,761** | **77.7%** | **12:02.2** (Algorithmic Pounce) |
| **Orlen (Star)** | 1,906 | 27 | 25 | 1,643 | **88.9%** | **12:02.1** |
| **EG Group (Esso)** | 3,506 | 12 | 13 | 903 | 26.5% | **12:03.8** (Delayed Bot) |
| **Couche-Tard (Total)** | 2,934 | 13 | 17 | 23 | 1.8% | **12:03.9** |
| **Oilinvest (HEM)** | 1,388 | 5 | 29 | 203 | 17.1% | **12:04.1** |
| **Eni (Agip)** | 1,525 | 9 | 28 | 0 | 2.4% | **12:06.5** |
| **Independents / Small** | 7,857 | 1,058 | 2,366 | 1,428 | 61.8% | **12:02.8** |

### The Noon Micro-Playbook:
1. **Shell Opens (Minute 0):** Shell triggers price hikes immediately at 12:00:15–12:00:50.
2. **Aral Synchronized Push (Minute 1):** At exactly 12:01:00, Aral's central cloud platform updates 100% of its stations nationwide simultaneously.
3. **JET's Algorithmic Pounce (Minute 2):** JET registers zero hikes at 12:00 or 12:01. Its pricing algorithms wait ~60–90 seconds for MTS-K API feeds to confirm Aral and Shell's new prices, then fire nationwide at 12:02:xx, pricing **consistently -2.0 ct/L below Aral/Shell**.
4. **Laggards (Minutes 3–7):** Esso, Total, HEM, and Eni trail behind, finalizing prices only after the Aral-Shell-JET anchor is established.

---

## Follower Postures & Price Undercutting Dynamics

When a station reacts to a neighboring competitor within 2.5 km (30s to 45m latency window):

| Follower Brand | Share Undercutting (< -0.5 ct) | Share Matching (±0.5 ct) | Share Higher (> +0.5 ct) | Median Spread vs Leader | Median Reaction Time |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Stonepeak (JET)** | **81.5%** | 13.6% | 4.9% | **-2.0 ct / L** | **19.3 min** |
| **Independents / Small** | **78.3%** | 14.0% | 7.7% | **-2.0 ct / L** | **19.2 min** |
| **BFT (Independent Assoc.)** | **73.6%** | 17.5% | 8.9% | **-2.0 ct / L** | **19.2 min** |
| **Oilinvest (HEM / Tamoil)** | **73.5%** | 17.5% | 9.0% | **-2.0 ct / L** | **18.3 min** |
| **EG Group (Esso)** | 42.0% | 21.8% | 36.2% | **0.0 ct / L** | **17.2 min** |
| **Shell** | 38.2% | 22.2% | 39.6% | **0.0 ct / L** | **19.4 min** |
| **Couche-Tard (Total)** | 37.9% | 23.9% | 38.2% | **0.0 ct / L** | **20.4 min** |
| **BP (Aral)** | 28.6% | 19.7% | **51.7%** | **+1.0 ct / L** | **22.4 min** |

### Three Clear Corporate Archetypes:
1. **The App-Ranking Discounters (JET, HEM, BFT, Independents):** Under-cut competitors by exactly **-2.0 ct/L** 74%–82% of the time to capture top positions on consumer comparison apps (Clever-Tanken, ADAC, Google Maps).
2. **The Cournot Matchers (Shell, Total, Esso):** Median spread of **0.0 ct/L**; match leaders to prevent margin-eroding price wars.
3. **The Premium Monopolist (Aral):** Stays **+1.0 ct/L more expensive** in >51% of interactions, monetizing brand equity, Rewe To Go convenience stores, and commercial fleet cards (Aral Card).

---

## Statutory Compliance Forensics (§ 3 KPAnG Audit)

### 1. Cutoff Sensitivity & API Transmission Latency
- **Strict 12:05 Cutoff (Letter of the Law):** 513,240 flagged hikes. Falsely classifies 4,043 stations as chronic violators due to **5–12 minute transmission queue latency** at MTS-K / Tankerkönig.
- **Buffer 12:15 Cutoff (+10 Min Queue Buffer):** 51,617 flagged hikes (90% drop in false positives).
- **Standard 13:00 Cutoff (Forensic Baseline):** 23,737 true off-hour hikes. Eliminates midday operational drift.

### 2. Market-Wide Compliance Funnel (17,866 Stations)
- **Tier 0 (100% Compliant):** 13,384 stations (**74.91%**) — 0 off-hour hikes across 5.5 months.
- **Tier 1 (Isolated Latency / Human Slip):** 2,751 stations (**15.40%**) — 1 to 2 hikes over 170 days.
  - *Combined Clean Baseline:* **90.31% of the German market is practically compliant.**
- **Tier 2 (Sporadic):** 1,336 stations (**7.48%**) — 3 to 10 hikes.
- **Tier 3 (Frequent Repeat Offenders):** 337 stations (**1.89%**) — 11 to 50 hikes.
- **Tier 4 (Chronic / Algorithmic Bot):** 58 stations (**0.32%**) — >50 hikes.
- *Concentration of Violations:* Tiers 3 and 4 (**395 stations, 2.21% of market**) generate **56.9% of all illegal price hikes in Germany**.

### 3. "Just Late" vs. True "2nd Raise on Same Day"
Applying strict intent filters separates operational delay from deliberate evasion:
- **"Just Late" (Human Delay, No Algo):** 437 stations had zero hikes at noon and executed only 1 single delayed price hike (e.g. at 13:30 or 14:15). They did not capture an extra hike.
- **"The 2nd Raise" (Definite Intent):** Stations that executed their primary statutory hike at noon AND executed a second price hike on the same day.
  - Only **173 stations** did this on $\ge 3$ distinct dates.
  - **Sustained 2nd Raises (Price stayed up): Only 55 stations (0.31% of Germany).**
    - 33 Independent / Small Operators (unmanned 24h commercial fleet cards like *Tankpool24*, *DS Card+Drive*).
    - 12 EG Group (Esso) stations.
    - 4 BFT, 3 Raiffeisen/BayWa.
    - **0 Oil Majors** (Aral, Shell, Total, Jet have hard zero sustained 2nd raises).
  - **Flash Rebounds (Corrected within $\le 10$ min): 76 stations.**
    - **EG Group (Esso) accounts for 56 of the 76 stations (73.7%).**
    - Demonstrates an algorithmic step-down bug: the bot drops price in the afternoon, overshoots or recalculates, bounces up by +2 ct for 2–5 minutes, and then continues downward.

---

## Spatial Proximity & The "One Bad Apple" Phenomenon

Using geodesic Haversine distance matrices across all 17,829 valid geocoded stations:

```
Distance from Repeat Offender (N=395) to:
  - Nearest Competitor (Any Brand):       Median 0.98 km (Mean 1.71 km)
  - Nearest 100% Clean Competitor:        Median 1.25 km (Mean 2.06 km)
  - Nearest OTHER Repeat Offender:        Median 9.33 km (Mean 12.32 km)
```

- **87.6% of repeat offenders** have zero other repeat offenders within 3 km.
- **78.5% of repeat offenders** have zero other repeat offenders within 5 km.
- **DBSCAN Spatial Clustering ($\epsilon = 5.0\text{ km}, min\_samples = 2$):**
  - **78.5% (310 stations) are classified as solitary "Noise" (lone rogues).**
  - Only 21.5% (85 stations) belong to any multi-station group (39 micro-clusters).
  - In multi-station towns (Espelkamp, Freden, Schüttorf), all violating stations are owned by the **exact same company** (*Kaiser-Tankstelle*, *TAS*, *Hermann Eissing*) using a shared, misconfigured POS system. There is **no evidence of rival stations engaging in tit-for-tat retaliation**.

### Urban Density Balancing & Local Contamination Rates
Controlling for the "Population-at-Risk" (station density within 5 km):

| Density Regime | Repeat Offenders (N=395) | Mean Dist to Competitor | DBSCAN Solitary Rogue Rate | Local Contamination Rate |
| :--- | :--- | :--- | :--- | :--- |
| **Rural (<5 stations in 5 km)** | **188 (47.6%)** | 2.57 km | **88.3%** | **25% – 50% of local market** |
| **Suburban / Small Town (5–15 in 5 km)** | **145 (36.7%)** | 1.09 km | **69.7%** | **6% – 20% of local market** |
| **Dense Urban (>15 stations in 5 km)** | **62 (15.7%)** | 0.53 km | **69.4%** | **< 1.5% of local market** |

**Conclusion:** Large metropolitan centers (Berlin, Munich, Hamburg, Cologne) are virtually clean because corporate enterprise cloud systems enforce strict compliance locks. Violations are concentrated in **rural transit corridors and small-town micro-monopolies**, where lone rogues exploit the fact that local competitors are legally constrained and regulatory enforcement is absent.

