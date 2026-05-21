# German Fuel Market Structure & Corporate Ownership

When analyzing the German gasoline market, it is critical to understand the underlying corporate networks. Many brands that appear as independent competitors are actually secondary or discount arms of massive multinational parent companies. 

If building a RAG pipeline or analyzing competitive pricing behavior (especially during policy shocks like the Tankrabatt), these brands must be mapped to their parent entities to avoid skewing the analysis.

## 1. The TotalEnergies / Couche-Tard (Circle K) Network
- **TOTALENERGIES** (Premium)
- **ELAN** (Discount)
- **The Connection:** ELAN is the official discount brand of TotalEnergies.
- **2024 Acquisition:** In January 2024, the Canadian convenience giant Alimentation Couche-Tard (Circle K) acquired 100% of the TotalEnergies and Elan network in Germany. They will continue to fly the "TotalEnergies" flag for the next 5 years (while Total supplies the fuel), but Couche-Tard is now the actual operator.

## 2. The Westfalen AG Group
- **WESTFALEN** (Premium)
- **MARKANT** (Discount)
- **The Connection:** Both are fully owned and operated by the Münster-based Westfalen AG. Westfalen operates premium stations under its own name, and uses Markant as its discount/secondary brand (acquired from Kuwait Petroleum in 2006).

## 3. The Eni S.p.A. (Italy) Network
- **AGIP ENI** (Premium)
- **SB** (Discount)
- **The Connection:** While "SB" technically stands for Selbstbedienung (Self-Service), Eni S.p.A. operates a massive portion of these as their budget brand ("SB-Tank" or "SB-Markttankstelle"). The corporate imprint of most SB stations traces back to Eni Deutschland.

## 4. The BP (British Petroleum) Empire
- **ARAL**
- **The Connection:** Aral is 100% owned by BP. Unlike in other countries where BP uses its own green logo, BP operates its fuel retail in Germany almost entirely under the Aral brand. They are the undisputed market leader.

## 5. The EG Group & ExxonMobil Partnership
- **ESSO**
- **The Connection:** Esso is historically the brand of ExxonMobil. However, in 2018, Exxon sold its entire German station network to the British multinational EG Group. EG Group operates the physical stations and sets retail strategies, while ExxonMobil strictly acts as the wholesale fuel supplier.

## 6. The Polish State Network
- **STAR / ORLEN**
- **The Connection:** Owned by the Polish state refiner Orlen. They traditionally operated exclusively as the discount brand "star" in Germany, but are currently undergoing a massive multi-year rebranding to convert them all to "Orlen."

## 7. The Cooperatives & Associations (Independent Umbrellas)
These must be treated differently in analysis. They are not single corporations dictating nationwide pricing, but rather umbrella organizations for independent mid-sized owners:
- **BFT (FREIE) & FREI:** Bundesverband Freier Tankstellen (Federal Association of Independent Petrol Stations). A lobby/umbrella group for independent mid-sized operators.
- **AVIA:** A cooperative (Genossenschaft) made up of dozens of independent, medium-sized mineral oil companies that pool resources to buy fuel and market under the unified red-and-white Avia brand.
- **RAIFFEISEN & BAYWA:** Stem from massive agricultural cooperatives. BayWa AG historically emerged from the Raiffeisen cooperative structure, and both tend to dominate rural/agricultural regions rather than Autobahns.

## 8. The Generic / Supermarket Group
- **SUPERMARKT & TANKCENTER**
- **The Connection:** These are data categorization tags from the MTS-K (Markttransparenzstelle). They represent stations physically tied to large grocery retailers (Kaufland, Globus, Famila, V-Markt). "Tankcenter" is specifically often tied to Edeka supermarkets.

## 9. The Oilinvest Group (Libyan State)
- **HEM**
- **T (Tamoil)**
- **The Connection:** Both HEM and Tamoil are owned by the Oilinvest Group, which was founded by the Libyan state to consolidate European energy assets. In our data, "T" and "HEM" should be grouped together under the Tamoil/Oilinvest umbrella.

## 10. The Mabanaft / Marquard & Bahls Group
- **CLASSIC**
- **CALPAM**
- **The Connection:** Both of these mid-sized networks operate under the umbrella of Mabanaft (Marquard & Bahls). Mabanaft historically owned **OIL!** as well, but the OIL! network was acquired by the British Prax Group in 2024.

## 11. The Singular Corporate Entities
These brands operate mostly autonomously under their respective parent companies:
- **SHELL:** Shell plc.
- **JET:** Historically Phillips 66. In late 2024, a deal was struck where Stonepeak acquired 65% and Phillips 66 retained 35%. They are known for being an aggressive price-discounter.
- **OIL!:** Acquired by the British Prax Group from Mabanaft in 2024.
