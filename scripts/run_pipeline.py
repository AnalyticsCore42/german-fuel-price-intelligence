"""
Script: run_pipeline.py
Description: The central orchestrator that runs all stages of the Germany Gas Price
             data preprocessing pipeline sequentially. Tracks per-step runtime and
             peak memory usage for profiling and comparison.
"""

import sys
import time
from pathlib import Path

# Add src/ to sys.path so we can import the gasprice package
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from gasprice.clean_stations import clean_station_data
from gasprice.update_brent_crude import update_macro_data
from gasprice.fetch_refined_product_baseline import build_refined_product_baseline
from gasprice.build_dashboard_dataset import build_dashboard_datasets, _get_rss_mb
from gasprice.station_price_stats import build_station_stats


def _run_step(step_num: int, total: int, label: str, func, *args) -> dict:
    """Run a pipeline step and return timing + memory stats."""
    print(f"\n[STEP {step_num}/{total}] {label}")
    rss_before = _get_rss_mb()
    t0 = time.perf_counter()
    func(*args)
    elapsed = time.perf_counter() - t0
    rss_after = _get_rss_mb()
    stats = {
        "step": step_num,
        "label": label,
        "seconds": elapsed,
        "rss_before_mb": rss_before,
        "rss_after_mb": rss_after,
        "rss_delta_mb": rss_after - rss_before,
    }
    print(f"  ⏱  {label}: {elapsed:.1f}s | RSS: {rss_before:.0f} → {rss_after:.0f} MB (Δ {rss_after - rss_before:+.0f} MB)")
    return stats


def main():
    pipeline_start = time.perf_counter()
    print("=" * 60)
    print("STARTING GAS PRICE ANALYSIS PIPELINE")
    print("=" * 60)
    print(f"Initial RSS: {_get_rss_mb():.0f} MB")

    stations_in = PROJECT_ROOT / "data" / "tankerkoenig" / "stations" / "latest-stations.parquet"
    stations_out = PROJECT_ROOT / "data" / "tankerkoenig" / "stations" / "cleaned-stations.parquet"

    step_stats = []
    step_stats.append(_run_step(1, 5, "Cleaning station metadata",
                                clean_station_data, str(stations_in), str(stations_out)))
    step_stats.append(_run_step(2, 5, "Updating Brent Crude & Exchange Rates",
                                update_macro_data))
    step_stats.append(_run_step(3, 5, "Fetching Refined Product Baselines",
                                build_refined_product_baseline))
    step_stats.append(_run_step(4, 5, "Building Dashboard Datasets",
                                build_dashboard_datasets))
    step_stats.append(_run_step(5, 5, "Building Station Price Stats",
                                build_station_stats))

    pipeline_elapsed = time.perf_counter() - pipeline_start
    peak_rss = max(s["rss_after_mb"] for s in step_stats)

    print("\n" + "=" * 60)
    print("PIPELINE EXECUTED SUCCESSFULLY")
    print("=" * 60)
    print(f"\n{'Step':<5} {'Label':<45} {'Time':>8} {'RSS After':>10}")
    print("-" * 70)
    for s in step_stats:
        print(f"{s['step']:<5} {s['label']:<45} {s['seconds']:>7.1f}s {s['rss_after_mb']:>9.0f} MB")
    print("-" * 70)
    print(f"{'':5} {'TOTAL':<45} {pipeline_elapsed:>7.1f}s {peak_rss:>9.0f} MB (peak)")


if __name__ == "__main__":
    main()
