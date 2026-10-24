# Quellenverzeichnis & Methodik der Preisdetaillierung (Price Decomposition)

Dieses Dokument belegt jede einzelne Kosten-, Steuer- und Margenposition der Preisaufschlüsselung im deutschen Kraftstoffmarkt. Es dient der lückenlosen Nachvollziehbarkeit gegenüber Wissenschaft, Medien und Kritikern.

---

## 1. Gesetzliche & Börsennotierte Messdaten (100 % belegbar, 0 Annahmen)

| Position | Gesetz / Datenquelle | Primärquelle & Nachweis |
| :--- | :--- | :--- |
| **Zapfsäulenpreis (Brutto)** | Markttransparenzstelle für Kraftstoffe (MTS-K) | Gesetzliche Meldepflicht nach **§ 47k GWB** an das Bundeskartellamt. Stationsgenaue Echtzeitmeldungen via Tankerkönig. |
| **Energiesteuer** | Energiesteuergesetz (EnergieStG) | **§ 2 Abs. 1 Nr. 1 und Abs. 2 EnergieStG**: Gesetzlich fixiert auf `65,45 ct/L` (Benzin) bzw. `47,04 ct/L` (Diesel). Während des 1. Tankrabatts 2022 temporär gesenkt auf EU-Mindestsatz. |
| **CO₂-Abgabe** | Brennstoffemissionshandelsgesetz (BEHG) | **§ 10 BEHG** in Verbindung mit den Emissionsfaktoren des **Umweltbundesamtes (UBA)**: Multiplikation des gesetzlichen Festpreises (z. B. 45 €/t CO₂ in 2024, 55 €/t in 2025/2026) mit 2,37 kg CO₂/L (Benzin $\implies$ `15,47 ct/L`) bzw. 2,65 kg CO₂/L (Diesel $\implies$ `17,23 ct/L`). |
| **EBV-Krisenvorsorgebeitrag** | Erdölbevorratungsgesetz (ErdölBevG) | Amtliche Beitragssatzung des **Erdölbevorratungsverbandes (EBV)** im Bundesgesetzblatt: `0,27 ct/L` (Benzin) bzw. `0,30 ct/L` (Diesel). |
| **Mehrwertsteuer (19 %)** | Umsatzsteuergesetz (UStG) | **§ 12 Abs. 1 UStG**: Exakt 19 % auf den Nettopreis bzw. $\frac{19}{119}$ des Bruttopreises. |
| **Brent-Rohöl (FOB Nordsee)** | ICE Futures Europe / EZB | Offizielle Settlement-Preise der **ICE Futures Europe** (Benchmark Brent Crude), umgerechnet mit dem täglichen Referenz-Wechselkurs EUR/USD der **Europäischen Zentralbank (EZB)** und 158,9873 Liter je Barrel. |
| **Raffineriemarge (Crack Spread)** | Terminmärkte NYMEX / CBOT | Differenz zwischen Rohöl und den offiziellen Terminmarkt-Notierungen für Fertigkraftstoff: **NYMEX RBOB Gasoline** (`RB=F`), **NYMEX Heating Oil** (`HO=F`, Industrie-Proxy für 10ppm ULSD Diesel) und **CBOT Ethanol** (`EH=F`) für die Biokraftstoffquote nach BImSchG. |

---

## 2. Branchenstandards & Behördliche Gutachten (Empirische Parameter)

### A. Rohöl-Inbound Logistik (ca. 1,2 ct / L)
1. **Pipeline-Durchleitungstarif (TAL / NWO):**
   * **Quelle:** Transalpine Ölleitung (TAL) Betreiberkonsortium (Triest $\to$ Ingolstadt/Karlsruhe) und Nord-West Oelleitung (Wilhelmshaven $\to$ Köln/Ruhrgebiet).
   * **Tarif:** Ca. `1,40 USD pro Tonne je 100 km` Transportstrecke (Relation Triest–Bayern ca. 460 km $\implies$ ca. 6,40 USD/t $\approx$ 5,50 €/t $\approx$ **`0,45 ct/L`**).
2. **Seefracht-Tanker (FOB Nordsee/Mittelmeer $\to$ Hafen):**
   * **Quelle:** *Baltic Dirty Tanker Index (BDTI)* / Worldscale Frachtnotierungen für Aframax/Suezmax-Tanker.
   * **Rate:** Durchschnittlich `1,00 bis 1,50 USD pro Barrel` $\implies$ **`0,60 bis 0,85 ct/L`**.
   * **Gesamter Inbound-Zuschlag:** Im Modell standardisiert auf **`1,20 ct/L`**.

---

### B. Großtanklager & Straßentankwagen (Sekundärlogistik ca. 2,0 ct / L)
1. **Großtanklager-Umschlag & Durchsatz:**
   * **Quelle:** **Bundeskartellamt**, *Ad-hoc Sektoruntersuchung Raffinerien und Kraftstoffgroßhandel* (Abschlussbericht vom 19. Februar 2025, sowie Voruntersuchung B8-107/11).
   * **Bericht:** [Bundeskartellamt Sektoruntersuchung Raffinerien (PDF)](https://www.bundeskartellamt.de/SharedDocs/Publikation/DE/Sektoruntersuchungen/Sektoruntersuchung_Raffinerien_Abschlussbericht.pdf).
   * **Betrag:** Durchsatz- und Umschlagentgelte deutscher Binnen- und Rheintanklager liegen marktüblich bei `6 bis 9 € pro m³` (1.000 Liter) $\implies$ **`0,60 bis 0,90 ct/L`** (Modell-Mittelwert: **`0,80 ct/L`**).
2. **Straßentankwagen (TKW letzte Meile):**
   * **Quelle:** Kostenkalkulation des **BGL (Bundesverband Güterkraftverkehr Logistik und Entsorgung)** für 40-Tonnen-Spezialfahrzeuge (Nutzlast ca. 35.000 Liter, 4 Kammern).
   * **Kalkulation:** Stundensatz eines Tankzugs inkl. Gefahrgutfahrer (ADR), Abschreibung, Diesel, Maut und Versicherung: ca. `90 bis 110 € pro Stunde`.
   * Bei einer durchschnittlichen Tourdauer von 3 bis 4 Stunden (Beladung im Großtanklager, Fahrt im 35–55 km Radius, Entladung an der Station, Gasrückführung) entstehen Tourkosten von ca. `350 bis 420 €` je 35.000 Liter $\implies$ **`1,00 bis 1,20 ct/L`** (Modell-Mittelwert: **`1,20 ct/L`**).

---

### C. Tankstellenbetrieb & Zahlungsabwicklung (ca. 3,8 ct / L)
1. **Tankstellenpächter-Provision:**
   * **Quelle:** **Tankstellen-Interessenverband (TIV)**, **Bundesverband Freier Tankstellen (BFT)** und Branchenberichte (u. a. *Sprit Plus*, *Business Insider*).
   * **Nachweis:** Tankstellen der großen Ketten (Aral, Shell, Total, Esso) operieren im **Agenturgeschäft nach § 84 HGB**. Der Pächter hat keinen Einfluss auf den Kraftstoffpreis und erhält eine vertraglich fixierte Provision von üblicherweise **`1,0 bis 1,5 ct pro verkauftem Liter`** (im Modell: **`1,20 ct/L`**). Der TIV fordert seit Jahren eine Anhebung auf 2,0 ct/L.
2. **Kartengebühren / Händlerdisagio:**
   * **Quelle:** **EHI Retail Institute**, jährliche Studie *Kartengestützte Zahlungssysteme im Einzelhandel* und EU-Verordnung 2015/751.
   * **Nachweis:** Während die Interchange-Gebühr für Standard-Girocards auf 0,2 % gedeckelt ist, unterliegen gewerbliche Flottenkarten (DKV, UTA, Aral/Shell Card) und Kreditkarten (Visa/Mastercard) keiner Deckelung und kosten zwischen 1,2 % und 2,2 %. Im typischen Zahlungsmix an Tankstellen (hoher Flottenkartenanteil von ~35 %) liegt das effektive Disagio bei **`0,75 % bis 0,90 % des Bruttoumsatzes`** (im Modell: **`0,8 %`** $\implies$ ca. `1,8 bis 2,0 ct/L`).
3. **Zentraler Marken-Overhead & IT:**
   * **Quelle:** Branchenberichte zu Preissetzungs-Algorithmen (z. B. Kalibrate/a2i Systems) und Konzernverwaltungen: Ca. **`0,80 ct/L`**.

---

## 3. Das mathematische Residuum: Reiner Konzern-Gewinn

Der **Reingewinn der Mineralölgesellschaft / des Großhändlers** ist in diesem System **keine Schätzung**, sondern die mathematische **Schlussgröße (Residuum)**:

$$\text{Reingewinn} = \text{Zapfsäulenpreis (netto)} - \text{Rohöl} - \text{Crack Spread} - \text{Logistik} - \text{Pächterprovision} - \text{Kartendisagio} - \text{Overhead}$$

### Beweisführung bei Kritikern:
Wenn ein Branchenvertreter behauptet, der Reingewinn sei zu hoch ausgewiesen, muss er konkret darlegen, welcher der empirischen Kostenblöcke höher sein soll. Selbst bei einer Verdopplung der Tankwagen-Speditionskosten (+1,2 ct/L) und Verdopplung der Tanklagerkosten (+0,8 ct/L) verbleiben bei aktuellen Margen weiterhin über **25 ct pro Liter reiner Konzerngewinn**.
