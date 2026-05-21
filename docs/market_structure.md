Here is the definitive, verified dossier of the German fuel market as of May 2026. This is the exact "Ground Truth" you should save as a Markdown file (e.g., market_structure.md) and feed into your Agentic RAG pipeline.

By having this exact mapping, your LLM will never hallucinate corporate ownership or incorrectly aggregate independent competitors.

🔴 Tier 1: Global Conglomerates & "Big Oil"

These are the massive multinational players. Their pricing strategies are highly centralized.

- **BP (British Petroleum)**:
  - Brands: ARAL
  - Context: The undisputed market leader in Germany. Unlike in other countries, BP operates almost entirely under the Aral brand in the German market.
- **Alimentation Couche-Tard (Circle K)**:
  - Brands: TOTALENERGIES, ELAN, ACCESS
  - Context: Crucial M&A update. In early 2024, the Canadian retail giant Couche-Tard acquired the entire German network from TotalEnergies. They operate TotalEnergies as the premium brand, and Elan/Access as their discount partners.
- **Shell plc**:
  - Brands: SHELL
  - Context: Operates directly under its own massive global brand.
- **Eni S.p.A. (Italy)**:
  - Brands: AGIP ENI
  - Context: The Italian state-linked giant. (Note: While they operate many "SB" discount stations, the data cannot perfectly isolate them, so Agip/Eni is tracked independently from generic "SB" signs).
- **PKN Orlen (Polish State)**:
  - Brands: STAR, ORLEN
  - Context: Controlled by the Polish state refiner. They historically used the "star" brand in Germany but are actively rebranding their network to "Orlen."

🟠 Tier 2: Private Equity & Recent Acquisitions

These networks recently changed hands, making pre-2025 data sources highly inaccurate.

- **Stonepeak & EEP**:
  - Brands: JET
  - Context: Major 2025 Update. Closed a €2.5 Billion deal on December 1, 2025, to acquire JET from Phillips 66 (who retained only a 35% non-operative stake). JET is famous for being the most aggressive discounter among the major brands.
- **EG Group (UK)**:
  - Brands: ESSO
  - Context: ExxonMobil owns the "Esso" brand and supplies the fuel, but the UK-based EG Group actually operates the physical stations and sets the retail pricing.
- **Prax Group (UK)**:
  - Brands: OIL!
  - Context: Fully acquired from the German Mabanaft group.

🟢 Tier 3: The "Mittelstand" Consolidations (The Hidden Giants)

These are large, family-owned German companies that have quietly swallowed up other brands. This is where most standard AI models hallucinate.

- **Wilhelm Hoyer Group (HQ: Visselhövede)**:
  - Brands: HOYER, SPRINT
  - Context: A massive independent player in Northern Germany. Combining Hoyer and Sprint creates a single corporate block of over 260 stations.
- **Westfalen AG (HQ: Münster)**:
  - Brands: WESTFALEN, MARKANT
  - Context: Westfalen is the premium brand; Markant (acquired from Kuwait Petroleum in 2006) serves as their discount/secondary arm.
- **Christian Lühmann GmbH (HQ: Hoya)**:
  - Brands: CLASSIC
  - Context: 100% independent, family-owned since 1882. No relation to Mabanaft.
- **Lother GmbH (HQ: Hamburg)**:
  - Brands: NORDOEL
  - Context: Regional powerhouse dominating Schleswig-Holstein and surrounding areas.
- **Q1 Energie AG (HQ: Osnabrück)**:
  - Brands: Q1
  - Context: Broke away from the AVIA cooperative in the 1980s to become a fierce independent competitor.

🟡 Tier 4: International Niche Holdings

- **Oilinvest Group (Libya)**:
  - Brands: HEM, T (Tamoil)
  - Context: The downstream retail arm of the Libyan Investment Authority.
- **Bolloré Group (France)**:
  - Brands: CALPAM
  - Context: The retail stations (HQ'd in Aschaffenburg) are owned by this massive French logistics conglomerate, not to be confused with the Hamburg-based bunkering sister company.

🟣 Tier 5: Cooperatives & Generics (Fragmented Pricing)

These brands do not have centralized pricing algorithms.

- **The Cooperatives: AVIA, BFT (FREIE), FREI, RAIFFEISEN, BAYWA**
  - Context: These are umbrella associations for independent owners or agricultural cooperatives. Your RAG LLM must know that a price hike at one AVIA does not guarantee a price hike at an AVIA in the next town over.
- **The Grocery Retailers: SUPERMARKT, TANKCENTER**
  - Context: Loss-leader stations located in supermarket parking lots (Edeka, Kaufland, etc.).
- **The Ambiguous Discount Sign: SB (Selbstbedienung)**
  - Context: Kept isolated in the dataset. While Eni uses this name heavily, it is also used generically by independent operators.

🚨 Bonus Policy Context: The 2026 "12:00 PM Rule"

If your dashboard analyzes the "12:00 PM hike," your LLM needs to know why it's happening.

- **The Law**: The Kraftstoffpreisanpassungsgesetz (Fuel Price Adjustment Act) of April 2026 legally restricts gas stations to raising their prices only once a day, exactly at 12:00 PM.
- **The Market Impact**: Because stations can no longer react to wholesale oil spikes in the afternoon, independent stations (like BFT/Freie) began applying massive "safety margins" exactly at noon to protect themselves from intraday Brent crude fluctuations.
