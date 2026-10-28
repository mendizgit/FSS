"""Paper-trade maths (domain/paper.py): levels, stop / target scan, settlement, flip tags."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from tss.domain import paper as pm

T0 = datetime(2026, 10, 28, 0, 0, tzinfo=UTC)


def bar(i: int, high: float, low: float, close: float) -> pm.Bar5:
    open_time = T0 + timedelta(minutes=5 * i)
    return pm.Bar5(open_time, open_time + timedelta(minutes=5), high, low, close)


def long_levels() -> pm.Levels:
    return pm.levels("long", 100.0, 50, 10, 1.0, 2.0, 0.0)


def test_levels_long_short_and_sizing() -> None:
    lv = long_levels()
    assert (lv.entry, lv.stop, lv.target) == (100.0, 99.0, 102.0)
    assert lv.notional == 500 and lv.qty == 5
    sh = pm.levels("short", 100.0, 50, 10, 1.0, 2.0, 0.0)
    assert (sh.stop, sh.target) == (101.0, 98.0)
    slipped = pm.levels("long", 100.0, 50, 10, 1.0, 2.0, 0.02)
    assert slipped.entry == pytest.approx(100.02)


def test_scan_target_stop_and_pessimistic_tie() -> None:
    lv = long_levels()
    hit = pm.scan("long", lv, [bar(0, 101, 99.5, 100.5), bar(1, 102.5, 100, 102)], 0.0)
    assert hit is not None and hit.reason == "target" and hit.price == 102.0
    assert hit.mfe_pct == pytest.approx(2.5)
    lose = pm.scan("long", lv, [bar(0, 100.5, 98.9, 99)], 0.0)
    assert lose is not None and lose.reason == "stop" and lose.price == 99.0
    both = pm.scan("long", lv, [bar(0, 103, 98, 100)], 0.0)
    assert both is not None and both.reason == "stop"
    assert pm.scan("long", lv, [bar(0, 101, 99.5, 100)], 0.0) is None


def test_scan_short_side() -> None:
    sh = pm.levels("short", 100.0, 50, 10, 1.0, 2.0, 0.0)
    win = pm.scan("short", sh, [bar(0, 100.5, 97.9, 98)], 0.0)
    assert win is not None and win.reason == "target"
    loss = pm.scan("short", sh, [bar(0, 101.2, 99.5, 101)], 0.0)
    assert loss is not None and loss.reason == "stop"


def test_settle_target_stop_and_fees() -> None:
    lv = long_levels()
    win = pm.settle("long", lv, 102.0, 1.0, 0.02)
    assert win.pnl == pytest.approx(10 - (100 + 102) * 5 * 0.0002)  # 10 gross - 0.202 fees
    assert win.r_multiple == pytest.approx(win.pnl / 5)
    lose = pm.settle("long", lv, 99.0, 1.0, 0.0)
    assert lose.pnl == pytest.approx(-5) and lose.r_multiple == pytest.approx(-1)
    short = pm.settle("short", pm.levels("short", 100.0, 50, 10, 1.0, 2.0, 0.0), 98.0, 1.0, 0.0)
    assert short.pnl == pytest.approx(10)


def test_market_exit_slips_against_trade_and_uses_last_bar() -> None:
    lv = long_levels()
    bars = [bar(0, 101, 99.5, 100.4), bar(1, 100.9, 99.8, 100.6)]
    out = pm.market_exit("long", "invalidated", bars, lv, 0.02)
    assert out.reason == "invalidated" and out.price == pytest.approx(100.6 * 0.9998)
    assert out.time == bars[-1].close_time


def test_flip_tags_side_aligned_and_window() -> None:
    events = [("BULL_T", 2), ("SELL", 1), ("BUY", 9)]
    text, ok = pm.flip_tags("long", events)
    assert text == "BULL_T:2,BUY:9" and ok
    text, ok = pm.flip_tags("short", events)
    assert text == "SELL:1" and ok
    assert pm.flip_tags("long", [("BUY", 9)]) == ("BUY:9", False)
    assert pm.flip_tags("long", []) == (None, False)


def test_open_at_blocks_alerts_raised_during_a_trade() -> None:
    t0 = datetime(2026, 10, 28, 8, 0, tzinfo=UTC)
    t1 = t0 + timedelta(minutes=30)
    assert pm.open_at(t0, t1, t0 + timedelta(minutes=10))  # alert while open
    assert pm.open_at(t0, None, t1)  # still open
    assert not pm.open_at(t0, t1, t1)  # raised as it closed
    assert not pm.open_at(t0, t1, t1 + timedelta(minutes=5))  # raised after the close
    assert not pm.open_at(t0, t1, t0 - timedelta(minutes=5))  # raised before the entry
