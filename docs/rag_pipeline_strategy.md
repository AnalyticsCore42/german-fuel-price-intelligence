# Future RAG Pipeline Plan

This file includes only the later plan for a natural-language query layer over the project data; brand, group, and ownership facts live in `docs/market_structure.md`.

## Status

The RAG pipeline is a future phase and is not implemented yet.

The dashboard already produces the structured datasets that a later RAG layer should query:

- `data/processed_daily_margins.parquet`: national daily prices, taxes, net product prices, and net product spreads.
- `data/processed_intraday.parquet`: reconstructed hourly national price patterns.
- `data/processed_brand_daily_margins.parquet`: daily margin comparison by visible brand buckets and ownership groups.

## Knowledge Sources

- `docs/market_structure.md`: brand, ownership, corporate-group mapping, and brand-analysis caveats.
- `docs/taxes_and_duties_history.md`: VAT, energy tax, CO2, EBV, and Tankrabatt tax constants.
- `docs/policy_timeline_tankrabatt.md`: legislative and policy milestone dates.
- The parquet datasets in `data/`: numerical evidence for price, tax, spread, rhythm, and brand comparisons.

## Intended Query Layer

Use DuckDB over the parquet files so the agent can answer natural-language questions with deterministic table operations before writing any explanation.

Planned views:

- `daily_margins`: national daily margin data from `processed_daily_margins.parquet`.
- `intraday_prices`: hourly rhythm data from `processed_intraday.parquet`.
- `brand_daily_margins`: brand and ownership comparison data from `processed_brand_daily_margins.parquet`.

## Example Questions To Support

- Which ownership groups widened net product spreads most during Tankrabatt 1?
- Did discount child brands behave differently from premium brands under the same owner?
- Was the 2026 Tankrabatt passed through differently by independent operators versus large corporate chains?
- Which visible brands have the highest noon price premium after the 2026 price-adjustment rule?
- How do selected brands or ownership groups compare after adjusting for taxes and Brent?

## Guardrails

- Use `docs/market_structure.md` for brand ownership and do not infer ownership from a model's memory.
- Treat `brand` and `owner` as separate analysis levels.
- Apply the grouping and caveat rules exactly as documented in `docs/market_structure.md`.
- If a raw brand is not covered by the structured data, refuse to guess its owner and ask for a mapping update.

## Later Implementation Steps

1. Add a DuckDB query module that opens the parquet files read-only.
2. Define approved SQL templates for common questions: pass-through, event windows, brand deltas, ownership comparisons, and intraday rhythm.
3. Add an LLM tool-calling layer that selects a query template and parameters.
4. Require every generated answer to cite the queried dataset, date window, fuel type, and comparison level.
5. Build a small evaluation set from the example questions above before exposing the feature in the dashboard.
