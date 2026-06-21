# German Fuel Brand And Ownership Ground Truth

This file includes the working mapping from visible German fuel-station brand names to ownership groups, the dashboard grouping rules, and the market-context notes needed for brand-level margin analysis.

## How This File Is Used

- `scripts/01_clean_stations.py` cleans raw station brands to uppercase names and assigns `corporate_group`.
- `scripts/04_build_dashboard_dataset.py` creates two dashboard comparison levels:
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

## Related 2026 Policy Context

The 2026 `12:00 PM rule` matters for brand analysis because it may affect independent and fragmented operators differently from larger centrally priced groups.

- Law: the Kraftstoffpreisanpassungsgesetz of April 2026 restricts stations to raising prices only once per day, at 12:00 PM.
- Market impact: because stations cannot freely react to afternoon wholesale movements, independent stations may apply larger safety margins at noon to protect against intraday Brent or wholesale volatility.
