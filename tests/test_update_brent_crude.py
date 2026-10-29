"""
Tests for parse_daily_bars in src/gasprice/update_brent_crude.py.

Why these tests matter:
Yahoo's newest daily bar is the open session. Without a flag, a thin Sunday-evening futures open
(Oct 25, 2026: 110.47 vs. Friday 116.72) read like a final 5% weekend drop. The value stays, marked partial.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from gasprice.update_brent_crude import parse_daily_bars


def _ts(*args) -> int:
    return int(datetime(*args, tzinfo=timezone.utc).timestamp())


def _result(bars, tz="America/New_York"):
    return {
        "meta": {"exchangeTimezoneName": tz},
        "timestamp": [_ts(*t) for t, _ in bars],
        "indicators": {"quote": [{"close": [c for _, c in bars]}]},
    }


def test_sunday_evening_open_is_kept_as_partial():
    result = _result([((2026, 10, 23, 4), 116.72), ((2026, 10, 25, 22), 110.47)])
    df = parse_daily_bars(result, now=datetime(2026, 10, 25, 22, 42, tzinfo=timezone.utc))
    assert df.rows() == [(date(2026, 10, 23), 116.72, False), (date(2026, 10, 25), 110.47, True)]


def test_todays_bar_is_partial_after_evening_reopen():
    # Thu 23:01 UTC = 19:01 New York: Thursday's bar already holds Friday-session trades.
    result = _result([((2026, 10, 28, 4), 115.32), ((2026, 10, 29, 4), 111.48)])
    df = parse_daily_bars(result, now=datetime(2026, 10, 29, 23, 1, tzinfo=timezone.utc))
    assert df["partial"].to_list() == [False, True]
    assert df["value"].to_list() == [115.32, 111.48]


def test_bars_are_dated_in_exchange_time_and_nulls_skipped():
    # EURUSD=X bar at 23:00 UTC during BST is the next London day.
    result = _result([((2026, 10, 22, 23), 1.1221), ((2026, 10, 26, 0), None)], tz="Europe/London")
    df = parse_daily_bars(result, now=datetime(2026, 10, 28, 12, tzinfo=timezone.utc))
    assert df.rows() == [(date(2026, 10, 23), 1.1221, False)]
