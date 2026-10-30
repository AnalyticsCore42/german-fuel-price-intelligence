"""
Tests for src/gasprice/pass_through_model.py.

Why these tests matter:
The pass-through estimate is the dashboard's headline claim about the Tankrabatt. On a synthetic
market with a known cost response and a known pass-through, these tests check that the calm-period
model recovers the response profile and the pass-through, that cost moves during the discount are not
mistaken for tax effects, and that the size of each cut comes from the tax engine.
"""
from __future__ import annotations

from datetime import date

import numpy as np
import polars as pl
import pytest

from gasprice.pass_through_model import (
    TAX_CUT_EVENTS,
    _prepare,
    cost_response_profile,
    energy_tax_cut,
    estimate_pass_through,
    fit_cost_response,
)

TR1, TR2, TR3 = TAX_CUT_EVENTS
# Share of a Brent / crack change reaching the net pump price at each lag (uniform within the
# model's lag buckets): Brent 60% within 7 days, 88% within 14; crack 35% within 7 days.
BRENT_KERNEL = {1: 0.1, 2: 0.1, 3: 0.1, 4: 0.1, 5: 0.1, 6: 0.1, **{k: 0.04 for k in range(7, 14)}}
CRACK_KERNEL = {2: 0.1, 3: 0.1, 4: 0.05, 5: 0.05, 6: 0.05}


def _synthetic(true_pass: float, brent_drop_at_start: float = 0.0, seed: int = 0) -> pl.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pl.date_range(date(2023, 1, 1), date(2026, 10, 23), "1d", eager=True).to_list()
    n = len(dates)
    db = rng.normal(0, 0.006, n)
    ds = rng.normal(0, 0.003, n)
    start = dates.index(TR3.start)
    db[start] -= brent_drop_at_start
    dp = rng.normal(0, 0.0005, n)
    for lag, w in BRENT_KERNEL.items():
        dp[lag:] += w * db[:-lag]
    for lag, w in CRACK_KERNEL.items():
        dp[lag:] += w * ds[:-lag]
    b = 0.45 + np.cumsum(db)
    s = 0.15 + np.cumsum(ds)
    p = 0.75 + np.cumsum(dp)
    in_event = np.array([TR3.start <= d <= TR3.end for d in dates])
    p[in_event] += (1 - true_pass) * energy_tax_cut(TR3, "petrol")
    return pl.DataFrame({"date": dates, "p": p, "c": b + s, "b": b})


def _variant(rows: list[dict], name: str) -> dict:
    return next(r for r in rows if r["variant"] == name)


def test_energy_tax_cut_sizes_come_from_tax_engine():
    assert energy_tax_cut(TR1, "petrol") == pytest.approx(0.2955)
    assert energy_tax_cut(TR1, "diesel") == pytest.approx(0.1404)
    assert energy_tax_cut(TR2, "petrol") == pytest.approx(0.1404)
    assert energy_tax_cut(TR3, "diesel") == pytest.approx(0.1404)


def test_recovers_cost_response_profile():
    data = _prepare(_synthetic(1.0))
    profile = cost_response_profile(fit_cost_response(data, data.calm), days=(7, 14))
    for direction in ("Brent up", "Brent down"):
        assert profile[direction][0] == pytest.approx(60, abs=5)
        assert profile[direction][1] == pytest.approx(88, abs=5)
    for direction in ("crack up", "crack down"):
        assert profile[direction][0] == pytest.approx(35, abs=6)


@pytest.mark.parametrize("true_pass", [0.5, 0.8, 1.0])
def test_recovers_known_pass_through(true_pass):
    rows = estimate_pass_through("e5", TR3, _synthetic(true_pass))
    for variant in ("headline", "pre_announcement", "full_period"):
        r = _variant(rows, variant)
        assert r["pass_through_pct"] == pytest.approx(true_pass * 100, abs=4)
        assert r["ci_low_pct"] <= r["pass_through_pct"] <= r["ci_high_pct"]
    assert _variant(rows, "headline")["statutory_ct"] == pytest.approx(16.71, abs=0.01)


def test_brent_drop_during_discount_is_not_counted_as_pass_through():
    # Brent falls 8 ct/L on the start day; the raw pump drop would overstate pass-through.
    rows = estimate_pass_through("e5", TR3, _synthetic(0.8, brent_drop_at_start=0.08))
    assert _variant(rows, "headline")["pass_through_pct"] == pytest.approx(80, abs=4)


def test_future_event_returns_nothing():
    series = _synthetic(1.0).filter(pl.col("date") < TR3.start)
    assert estimate_pass_through("e5", TR3, series) == []
