#!/usr/bin/env bash
# Snapshot the current pipeline-output Parquet files onto the data-latest
# branch as a single commit, without touching the working tree or whatever
# branch is currently checked out. Run this after scripts/run_pipeline.py.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

BRANCH=data-latest
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
  data/dashboard/tankrabatt_pass_through.parquet
)

for f in "${FILES[@]}"; do
  if [ ! -f "$f" ]; then
    echo "ERROR: $f not found. Run scripts/run_pipeline.py first." >&2
    exit 1
  fi
done

echo "==> Verifying dashboard and pipeline integrity with pytest..."
.venv/bin/python -m pytest tests/ -q


INDEX_FILE=$(mktemp -u)
export GIT_INDEX_FILE="$INDEX_FILE"
trap 'rm -f "$INDEX_FILE"' EXIT

for f in "${FILES[@]}"; do
  hash=$(git hash-object -w "$f")
  git update-index --add --cacheinfo 100644,"$hash",$f
done

tree=$(git write-tree)
commit=$(git commit-tree "$tree" -m "data snapshot $(date -u +%Y-%m-%dT%H:%M:%SZ)")
git update-ref "refs/heads/$BRANCH" "$commit"

echo "Updated local branch '$BRANCH' -> $commit"
echo "Run: git push --force origin $BRANCH"
