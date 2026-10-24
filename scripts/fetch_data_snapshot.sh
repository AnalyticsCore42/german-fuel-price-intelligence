#!/usr/bin/env bash
# Restore the latest pipeline-output Parquet files from the data-latest
# branch into the local data/ directory. Needed after a fresh clone, since
# these files are gitignored on main and only tracked on data-latest.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

REF=data-latest
if ! git show-ref --verify --quiet "refs/heads/$REF"; then
  git fetch origin "$REF" 2>/dev/null || true
  if git show-ref --verify --quiet "refs/remotes/origin/$REF"; then
    REF=origin/$REF
  else
    echo "ERROR: no local or remote '$REF' branch found." >&2
    exit 1
  fi
fi

FILES=(
  data/processed_brand_daily_margins.parquet
  data/processed_daily_margins.parquet
  data/processed_intraday.parquet
  data/processed_macro_baseline.parquet
  data/processed_refined_product_baseline.parquet
  data/processed_regional_daily_margins.parquet
  data/station_price_stats.parquet
  data/dashboard/compliance_daily_trend.parquet
  data/dashboard/compliance_lateness_distribution.parquet
  data/dashboard/compliance_station_rankings.parquet
)

for f in "${FILES[@]}"; do
  mkdir -p "$(dirname "$f")"
  git show "$REF:$f" > "$f"
  echo "Restored $f from $REF"
done
