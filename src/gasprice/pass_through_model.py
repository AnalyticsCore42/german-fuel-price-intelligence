"""
Module: pass_through_model.py
Description: Counterfactual estimate of how much of a fuel tax cut reached pump prices.

Method:
  1. Net pump price p = pump price minus VAT, energy tax, CO2 price and EBV levy, so the tax cut
     itself does not enter the series. Full pass-through leaves p unchanged.
  2. Cost response model, fitted on calm days only (no crisis, no high Brent volatility, no tax event):
       d_p[t] = a + weekday + sum over lag buckets of
                (Brent up, Brent down, crack up, crack down) changes, lags 0-27 days
     Brent and the crack spread (wholesale product minus Brent) get separate up/down lag profiles.
  3. Counterfactual: p from the start of the baseline window onward, moved only by the observed cost
     changes through the calm-period response. Not passed on = change in (p - counterfactual)
     between the baseline window and the window in force:
       pass-through = 1 - [mean gap during - mean gap baseline] / energy-tax cut (net)
     Baselines: the WINDOW_DAYS before the start (headline) and before the announcement (robust to
     price behaviour after the announcement); windows in force: first WINDOW_DAYS and full period.
  4. Uncertainty: the same estimate on placebo dates without a tax change (true effect 0), refitted
     without the placebo span. Events in calm markets get the calm-placebo 90% interval, events
     during a crisis the turbulent-placebo interval.

Placebo RMSE (pp of a 14.04 ct cut, 14+14 days): this model 7.5-7.6 calm, 13.7-16.6 turbulent;
current dashboard tile (raw pump change) 20-41; wholesale lagged 3 days 10.7.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import polars as pl

from gasprice.tax_engine import (
    DEFAULT_DIESEL_ENERGY_TAX,
    DEFAULT_PETROL_ENERGY_TAX,
    ENERGY_TAX_PERIODS,
    calculate_net_price,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
DAILY_FILE = DATA_DIR / "processed_daily_margins.parquet"
REGIONAL_FILE = DATA_DIR / "processed_regional_daily_margins.parquet"

FUELS = {"e5": "petrol", "e10": "petrol", "diesel": "diesel"}
LAG_BUCKETS = [(0, 0), (1, 1), (2, 2), (3, 3), (4, 6), (7, 13), (14, 20), (21, 27)]
MAX_LAG = LAG_BUCKETS[-1][1]
COST_DRIVERS = ("Brent up", "Brent down", "crack up", "crack down")
WINDOW_DAYS = 14
VAT_GROSS_UP = 1.19
VOL_WINDOW = 21               # trading days for the rolling Brent volatility
VOL_QUANTILE = 0.90           # above this share of 2015-2025 volatility a day counts as turbulent
CALM_PAD_DAYS = 14
PLACEBO_STEP_DAYS = 7
PLACEBO_START_OFFSET_DAYS = 400
POST_EVENT_EXCLUSION_DAYS = 30


@dataclass(frozen=True)
class TaxCutEvent:
    name: str
    announced: date
    start: date
    end: date


TAX_CUT_EVENTS = [
    TaxCutEvent("TR1", date(2022, 3, 24), date(2022, 6, 1), date(2022, 8, 31)),
    TaxCutEvent("TR2", date(2026, 4, 15), date(2026, 5, 1), date(2026, 6, 30)),
    TaxCutEvent("TR3", date(2026, 9, 18), date(2026, 10, 1), date(2026, 12, 31)),
]
# Other tax changes (2020 COVID VAT cut, incl. announcement).
OTHER_TAX_WINDOWS = [(date(2020, 6, 3), date(2021, 1, 31))]
# Market crises; Iran war dated by the Brent volatility spike (Mar 10 - Aug 26, 2026).
CRISIS_WINDOWS = [
    (date(2008, 9, 1), date(2009, 6, 30)),    # financial crisis
    (date(2020, 2, 20), date(2020, 6, 30)),   # COVID crash
    (date(2022, 2, 24), date(2022, 12, 31)),  # Ukraine war / energy crisis
    (date(2026, 3, 1), date(2026, 8, 31)),    # Iran war
]


def energy_tax_cut(event: TaxCutEvent, tax_type: str) -> float:
    """Net energy-tax reduction in EUR/L during the event, from the tax engine schedule."""
    period = next(p for p in ENERGY_TAX_PERIODS if p.start <= event.start <= p.end)
    if tax_type == "petrol":
        return DEFAULT_PETROL_ENERGY_TAX - period.petrol_rate
    return DEFAULT_DIESEL_ENERGY_TAX - period.diesel_rate


def tax_windows() -> list[tuple[date, date]]:
    return [(e.announced, e.end + timedelta(days=POST_EVENT_EXCLUSION_DAYS)) for e in TAX_CUT_EVENTS] + OTHER_TAX_WINDOWS


def load_series(fuel: str) -> pl.DataFrame:
    """Daily `date`, net pump price `p`, wholesale product cost `c` and Brent `b` (EUR/L).

    The pump price is the station-count-weighted national average, as shown on the dashboard.
    """
    daily = pl.read_parquet(DAILY_FILE).select("date", f"price_{fuel}", f"{fuel}_product_eur_liter", "brent_eur_liter")
    if REGIONAL_FILE.exists():
        regional = pl.read_parquet(REGIONAL_FILE).filter(pl.col("region") != "Unknown Region")
        weighted = regional.group_by("date").agg(
            ((pl.col(f"price_{fuel}") * pl.col("station_count")).sum() / pl.col("station_count").sum()).alias("_w")
        )
        daily = daily.join(weighted, on="date", how="left").with_columns(
            pl.coalesce("_w", f"price_{fuel}").alias(f"price_{fuel}")
        ).drop("_w")
    full_range = pl.DataFrame({"date": pl.date_range(daily["date"].min(), daily["date"].max(), "1d", eager=True)})
    daily = full_range.join(daily, on="date", how="left").with_columns(pl.exclude("date").forward_fill())
    net = calculate_net_price(daily, "date", f"price_{fuel}", FUELS[fuel])
    return net.select(
        "date",
        pl.col("Net_Product_Price").alias("p"),
        pl.col(f"{fuel}_product_eur_liter").alias("c"),
        pl.col("brent_eur_liter").alias("b"),
    ).sort("date")


@dataclass
class _Data:
    dates: np.ndarray        # datetime64[D]
    p: np.ndarray
    X: np.ndarray
    y: np.ndarray
    turbulent: np.ndarray    # bool per day: crisis window or high Brent volatility (padded)
    calm: np.ndarray         # bool per day: usable for fitting


def _in_windows(dates: np.ndarray, windows, pad: int = 0) -> np.ndarray:
    out = np.zeros(len(dates), dtype=bool)
    for lo, hi in windows:
        out |= (dates >= np.datetime64(lo - timedelta(days=pad))) & (dates <= np.datetime64(hi + timedelta(days=pad)))
    return out


def _high_volatility(dates: np.ndarray, b: np.ndarray) -> np.ndarray:
    weekday = (dates.astype("datetime64[D]").view("int64") - 4) % 7 < 5   # 1970-01-01 was a Thursday
    trading = np.where(weekday)[0]
    ret = np.diff(np.log(b[trading]))
    vol = np.full(len(trading), np.nan)
    for k in range(VOL_WINDOW, len(trading)):
        vol[k] = ret[k - VOL_WINDOW:k].std() * np.sqrt(252) * 100
    years = dates[trading].astype("datetime64[Y]").astype(int) + 1970
    ref = vol[(years >= 2015) & (years <= 2025) & ~np.isnan(vol)]
    threshold = np.quantile(ref if len(ref) > 100 else vol[~np.isnan(vol)], VOL_QUANTILE)
    high = np.zeros(len(dates), dtype=bool)
    for k in trading[np.nan_to_num(vol, nan=0.0) > threshold]:
        high[max(0, k - CALM_PAD_DAYS):k + CALM_PAD_DAYS + 1] = True
    return high


def _prepare(series: pl.DataFrame) -> _Data:
    dates = series["date"].to_numpy().astype("datetime64[D]")
    p, c, b = (series[col].to_numpy().astype(float) for col in ("p", "c", "b"))
    n = len(p)
    t = np.arange(MAX_LAG + 1, n)
    features = []
    for x in (b, c - b):
        dx = np.concatenate([[0.0], np.diff(x)])
        for part in (np.maximum(dx, 0.0), np.minimum(dx, 0.0)):
            cs = np.concatenate([[0.0], np.cumsum(part)])
            for lo, hi in LAG_BUCKETS:
                f = np.zeros(n)
                f[t] = cs[t - lo + 1] - cs[t - hi]   # sum of part[t-hi .. t-lo]
                features.append(f)
    weekday = (dates.view("int64") - 4) % 7
    X = np.column_stack([np.ones(n)] + [(weekday == k).astype(float) for k in range(6)] + features)
    y = np.concatenate([[0.0], np.diff(p)])
    turbulent = _in_windows(dates, CRISIS_WINDOWS, CALM_PAD_DAYS) | _high_volatility(dates, b)
    calm = ~turbulent & ~_in_windows(dates, tax_windows(), CALM_PAD_DAYS)
    calm[:MAX_LAG + 1] = False
    return _Data(dates, p, X, y, turbulent, calm)


def fit_cost_response(data: _Data, mask: np.ndarray) -> np.ndarray:
    beta, *_ = np.linalg.lstsq(data.X[mask], data.y[mask], rcond=None)
    return beta


def cost_response_profile(beta: np.ndarray, days=(1, 3, 7, 14, 28)) -> dict[str, list[float]]:
    """Cumulative share (%) of a cost move that reaches the net pump price after n days."""
    coefs = beta[7:].reshape(len(COST_DRIVERS), len(LAG_BUCKETS))
    out = {}
    for name, row in zip(COST_DRIVERS, coefs):
        per_lag = np.concatenate([[row[j]] * (hi - lo + 1) for j, (lo, hi) in enumerate(LAG_BUCKETS)])
        out[name] = [float(np.cumsum(per_lag)[d - 1] * 100) for d in days]
    return out


def _pass_through(data: _Data, beta: np.ndarray, pre: tuple[int, int], post: tuple[int, int], cut: float) -> float:
    """Pass-through (%) for index windows pre=(i0, i1), post=(j0, j1), inclusive."""
    origin = pre[0] - 1
    p_hat = data.p[origin] + np.cumsum(data.X[origin + 1:post[1] + 1] @ beta)
    gap = data.p[origin + 1:post[1] + 1] - p_hat
    pre_gap = gap[:pre[1] - origin].mean()
    post_gap = gap[post[0] - origin - 1:].mean()
    return (1 - (post_gap - pre_gap) / cut) * 100


def placebo_errors(data: _Data, pre_len: int, gap: int, post_len: int, cut: float) -> tuple[np.ndarray, np.ndarray]:
    """Errors (pp) of the same window layout on dates without a tax change, split calm/turbulent."""
    span = pre_len + gap + post_len
    blocked = _in_windows(data.dates, tax_windows(), POST_EVENT_EXCLUSION_DAYS)
    calm_err, turb_err = [], []
    for i in range(PLACEBO_START_OFFSET_DAYS, len(data.p) - span, PLACEBO_STEP_DAYS):
        if blocked[i:i + span].any():
            continue
        train = data.calm.copy()
        train[max(0, i - MAX_LAG):i + span + MAX_LAG] = False
        beta = fit_cost_response(data, train)
        pre = (i, i + pre_len - 1)
        post = (i + pre_len + gap, i + span - 1)
        err = _pass_through(data, beta, pre, post, cut) - 100
        (turb_err if data.turbulent[i:i + span].any() else calm_err).append(err)
    return np.array(calm_err), np.array(turb_err)


def estimate_pass_through(fuel: str, event: TaxCutEvent, series: pl.DataFrame | None = None) -> list[dict]:
    """Pass-through estimates with 90% placebo intervals for the baseline/window variants."""
    series = load_series(fuel) if series is None else series
    data = _prepare(series)
    last_day = min(event.end, series["date"].max())
    if event.start > last_day:
        return []
    cut = energy_tax_cut(event, FUELS[fuel])
    index = {d: i for i, d in enumerate(data.dates.astype(object))}
    s, a, e = index[event.start], index[event.announced], index[last_day]
    w = WINDOW_DAYS
    variants = {
        "headline": ((s - w, s - 1), (s, min(e, s + w - 1))),
        "pre_announcement": ((a - w, a - 1), (s, min(e, s + w - 1))),
        "full_period": ((s - w, s - 1), (s, e)),
    }
    beta = fit_cost_response(data, data.calm & (np.arange(len(data.p)) < a - MAX_LAG))
    rows = []
    for variant, (pre, post) in variants.items():
        estimate = _pass_through(data, beta, pre, post, cut)
        calm_err, turb_err = placebo_errors(data, pre[1] - pre[0] + 1, post[0] - pre[1] - 1, post[1] - post[0] + 1, cut)
        turbulent = bool(data.turbulent[pre[0]:post[1] + 1].any())
        errors = turb_err if turbulent and len(turb_err) >= 20 else calm_err
        lo, hi = np.percentile(errors, [5, 95]) if len(errors) >= 20 else (np.nan, np.nan)
        rows.append({
            "event": event.name,
            "fuel": fuel,
            "variant": variant,
            "pass_through_pct": estimate,
            "ci_low_pct": estimate - hi,
            "ci_high_pct": estimate - lo,
            "market": "turbulent" if turbulent else "calm",
            "statutory_ct": cut * VAT_GROSS_UP * 100,
            "passed_ct": estimate / 100 * cut * VAT_GROSS_UP * 100,
            "pre_window": (data.dates[pre[0]].item(), data.dates[pre[1]].item()),
            "post_window": (data.dates[post[0]].item(), data.dates[post[1]].item()),
            "placebos": len(errors),
        })
    return rows


def estimate_all() -> pl.DataFrame:
    rows = []
    for fuel in FUELS:
        series = load_series(fuel)
        for event in TAX_CUT_EVENTS:
            rows.extend(estimate_pass_through(fuel, event, series))
    return pl.DataFrame(rows)


def main() -> None:
    for fuel in ("e5", "diesel"):
        data = _prepare(load_series(fuel))
        beta = fit_cost_response(data, data.calm)
        print(f"{fuel}: pump response to cost moves, calm days ({int(data.calm.sum())}), after 1/3/7/14/28 days")
        for name, values in cost_response_profile(beta).items():
            print(f"  {name:10} " + " ".join(f"{v:5.0f}%" for v in values))
    df = estimate_all()
    print(f"\npass-through, 90% placebo interval  (14 = first {WINDOW_DAYS} days in force)")
    print(f"{'fuel':7}{'event':6}{'market':10}{'14 vs 14 before start':>24}{'14 vs 14 before announc.':>27}{'full period':>20}")
    for (fuel, event), g in df.group_by(["fuel", "event"], maintain_order=True):
        cells = []
        for v in ("headline", "pre_announcement", "full_period"):
            r = g.filter(pl.col("variant") == v).row(0, named=True)
            cells.append(f"{r['pass_through_pct']:4.0f}% [{r['ci_low_pct']:3.0f}–{r['ci_high_pct']:3.0f}]")
        market = g.filter(pl.col("variant") == "headline")["market"].item()
        print(f"{fuel:7}{event:6}{market:10}{cells[0]:>24}{cells[1]:>27}{cells[2]:>20}")


if __name__ == "__main__":
    main()
