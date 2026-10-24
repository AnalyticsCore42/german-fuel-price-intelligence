# Policy Timeline: German Fuel Tax Discounts (Tankrabatte)

Source of truth for all legislative milestone dates used in the Event Study analysis.
These dates are used to draw policy phase markers in `ui/04_app.py`.

---

## Tankrabatt 1 — 2022 (Kabinett Scholz / Ampel-Koalition)

**Trigger:** Strongly rising fuel prices following the Russian invasion of Ukraine (Feb 24, 2022).
**Initiator:** Federal Finance Minister Christian Lindner (FDP).

| Date           | Phase          | Event                                                                                               |
|----------------|----------------|-----------------------------------------------------------------------------------------------------|
| Mar 14, 2022   | Public Rumour  | First public proposal by Lindner for a blanket "Tankrabatt" for all consumers.                      |
| Mar 24, 2022   | Official Ann.  | Federal government officially announces the measure. Coalition leaders agree on the second relief package ("zweites Entlastungspaket"), explicitly including the temporary energy tax cut on fuels. |
| May 10, 2022   | Draft Law      | Concrete legislative draft (Energiesteuersenkungsgesetz) formally submitted to the Bundestag by the coalition parties. |
| May 19, 2022   | Parliamentary  | Bundestag passes the law. Legal certainty from this date: effective date of June 1 confirmed.       |
| **Jun 1, 2022**  | **Effective**  | **Law takes effect. Energy tax cut begins.**                                                       |
| **Aug 31, 2022** | **Expiry**     | **Last day of the tax discount.**                                                                  |
| Sep 1, 2022    | Restoration    | Energy tax fully restored to standard rates.                                                        |

### Tax Changes (Tankrabatt 1)

| Fuel    | Standard Energy Tax | Reduced Rate (Jun–Aug 2022) | Reduction  | incl. 19% VAT |
|---------|--------------------|-----------------------------|------------|---------------|
| Petrol  | €0.6545 / L        | €0.3590 / L                 | −€0.2955/L | −**€0.3516/L** |
| Diesel  | €0.4704 / L        | €0.3300 / L                 | −€0.1404/L | −**€0.1671/L** |

**Anticipation window analysis:**
- Day −79 (Mar 14): Rumour enters public discourse. Speculative market reaction possible.
- Day −69 (Mar 24): Official government announcement. Market has high confidence the cut will happen.
- Day −22 (May 10): Draft law submitted. Effective date and magnitude known precisely.
- Day −13 (May 19): Bundestag vote. **Legal certainty.** No remaining regulatory risk.
- Day 0  (Jun 1):   Effective date.

The critical observation is that rational markets should have priced in the discount progressively
from Mar 24 onward, with the final adjustment at May 19 (legal finality) being the last possible
moment for residual price compression. Any remaining spread compression after Jun 1 represents
delayed or opportunistic pass-through.

---

## Tankrabatt 2 — 2026 (Kabinett Merz / CDU/CSU–SPD Koalition)

**Trigger:** High oil prices following the Iran-Israel conflict escalation (Iran War).
**Initiator:** Federal Finance Minister Lars Klingbeil (SPD).

| Date           | Phase         | Event                                                                                               |
|----------------|---------------|-----------------------------------------------------------------------------------------------------|
| Apr 15, 2026   | Draft Law     | After prior coalition committee agreement, the Federal Finance Ministry (BMF) finalises the draft and publicly announces the May 1 start date for the first time with concrete specifics. |
| Apr 24, 2026   | Parliamentary | Bundestag passes the law. Bundesrat approves in an emergency session the same day.                  |
| **May 1, 2026**  | **Effective** | **Law takes effect. Energy tax cut begins.**                                                       |
| **Jun 30, 2026** | **Expiry**   | **Last day of the tax discount.**                                                                  |
| Jul 1, 2026    | Restoration   | Energy tax restored to standard rates (planned).                                                    |

### Tax Changes (Tankrabatt 2)

| Fuel    | Standard Energy Tax | Reduced Rate (May–Jun 2026) | Reduction  | incl. 19% VAT |
|---------|--------------------|-----------------------------|------------|---------------|
| Petrol  | €0.6545 / L        | €0.5141 / L                 | −€0.1404/L | −**€0.1671/L** |
| Diesel  | €0.4704 / L        | €0.3300 / L                 | −€0.1404/L | −**€0.1671/L** |

> **Note on Diesel (Tankrabatt 2):** Both fuels were cut by the same absolute amount (14.04 ct/L net),
> consistent with `src/gasprice/tax_engine.py` and `docs/taxes_and_duties_history.md`.

**Anticipation window analysis:**
- Day −16 (Apr 15): First concrete public announcement with May 1 start date confirmed.
- Day −7  (Apr 24): Bundestag + Bundesrat vote. **Legal certainty.**
- Day 0   (May 1):  Effective date.

The 2026 window is much shorter (16 days vs 79 days in 2022), limiting the anticipation period
and theoretically reducing the opportunity for pre-emptive price compression.

---

## Tankrabatt 3 — Q4 2026 (Kabinett Merz / CDU/CSU–SPD Koalition)

**Trigger:** Renewed high fuel prices due to the ongoing Middle East (Iran) war.
**Initiator:** Federal government (BMF, Lars Klingbeil) after a federal–state agreement.
**Legal vehicle:** Inserted as an amendment (*Änderungsantrag*) into the insurance supervision
bill (VSAAG) rather than passed as a standalone law. Re-activates the Tankrabatt 2 rates essentially unchanged.

| Date           | Phase         | Event                                                                                               |
|----------------|---------------|-----------------------------------------------------------------------------------------------------|
| Sep 18, 2026   | Official Ann. | Federal government and states (Bund-Länder) agree to cut the energy tax on petrol and diesel again for Oct 1 – Dec 31, 2026. |
| Sep 25, 2026   | Parliamentary | Bundestag passes the amendment (roll-call vote: 434 yes, 128 no). Bundesrat approves the same day. **Legal certainty.** |
| ~Sep 28, 2026  | Signed        | Federal President Frank-Walter Steinmeier signs the law.                                            |
| **Oct 1, 2026**  | **Effective** | **Law takes effect. Energy tax cut begins.**                                                       |
| **Dec 31, 2026** | **Expiry**   | **Last day of the tax discount.**                                                                  |
| Jan 1, 2027    | Restoration   | Energy tax restored to standard rates (planned).                                                    |

### Tax Changes (Tankrabatt 3)

| Fuel    | Standard Energy Tax | Reduced Rate (Oct–Dec 2026) | Reduction  | incl. 19% VAT |
|---------|--------------------|-----------------------------|------------|---------------|
| Petrol  | €0.6545 / L        | €0.5141 / L                 | −€0.1404/L | −**€0.1671/L** |
| Diesel  | €0.4704 / L        | €0.3300 / L                 | −€0.1404/L | −**€0.1671/L** |

**Fiscal cost:** ~€2.34–2.5 bn (BMF: €2.34 bn revenue loss; other sources: ~€2.5 bn).
**Pass-through monitoring:** The mineral oil industry committed to passing on the cut from day one;
compliance is observable via the real-time price reports to the Markttransparenzstelle für Kraftstoffe (MTS-K).

**Anticipation window analysis:**
- Day −13 (Sep 18): Bund-Länder agreement, start date and magnitude known.
- Day −6  (Sep 25): Bundestag + Bundesrat vote. **Legal certainty.**
- Day 0   (Oct 1):  Effective date.

Note that the Tankrabatt 3 start (Oct 1) falls only 3 months after the Tankrabatt 2 expiry (Jul 1),
so the pre-event baseline window overlaps the Tankrabatt 2 period and its aftermath.

---

## Comparison of Policy Timelines

| Metric                       | Tankrabatt 1 (2022)   | Tankrabatt 2 (2026)   | Tankrabatt 3 (Q4 2026) |
|------------------------------|-----------------------|-----------------------|------------------------|
| First public signal → Effective date | ~79 days   | ~16 days              | ~13 days               |
| Legal certainty → Effective date     | 13 days    | 7 days                | 6 days                 |
| Duration                             | 3 months   | 2 months              | 3 months               |
| Petrol relief (incl. VAT)            | −35.16 ct/L | −16.71 ct/L          | −16.71 ct/L            |
| Diesel relief (incl. VAT)            | −16.71 ct/L | −16.71 ct/L          | −16.71 ct/L            |

---

## Notes on Incentive Asymmetries

### At Discount Start (Tax Cut)
- Competitive markets may discount **before** t=0 as stations race for market share.
- Longer anticipation windows (2022) give more time for pre-emptive competition.
- Expected spread behavior: declining inside pre-event zone, then flat or small additional drop at t=0.

### At Discount End (Tax Hike / Restoration)
- Oligopolistic incentive: stations have every reason to **pre-raise** prices before the restoration date.
- If prices rise in the days before t=0, the "official" jump at t=0 looks smaller than the full statutory amount.
- This is the **"rockets and feathers"** asymmetry documented by the Bundeskartellamt (Federal Cartel Office).
- The Bundeskartellamt's 2011 report "Kraftstoffpreise — Struktur, Preisbildung und Wettbewerb" explicitly describes this behavior.

---

*Last updated: 2026-10-24*
*Source: Bundestag Drucksachen, BMF press releases, official government communications.*
