"""FGI strategy paper trading: entry plan and partial-exit maths, strategy signal series."""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

import pytest

from tss.domain import fgi_paper as fm
from tss.indicators import fgi_strategy as fs

T0 = datetime(2026, 10, 28, 12, 0, tzinfo=UTC)
BAR = timedelta(minutes=5)


def bar(k: int, o: float, h: float, lo: float, c: float) -> fm.Bar5:
    return fm.Bar5(T0 + k * BAR, T0 + (k + 1) * BAR, o, h, lo, c)


def plan_long(**kw: float) -> fm.Plan:
    out = fm.plan(
        "long",
        100.0,
        1.0,
        98.0,
        100.0,
        margin=50,
        leverage=10,
        stop_cap_pct=kw.get("cap", 2.0),
        tp1_atr=1.5,
        tp2_atr=3.5,
        slippage_pct=0.0,
    )
    assert out is not None
    return out


def state(p: fm.Plan, side: str = "long") -> fm.State:
    return fm.State(side, p.entry, p.stop, p.stop, p.tp1, p.tp2, p.qty)


def run(st: fm.State, bars: list[fm.Bar5], edges: dict[datetime, fm.Boundary] | None = None):
    return fm.advance(st, bars, edges or {}, tp1_fraction=0.5, slippage_pct=0.0, fee_pct=0.0)


def test_plan_caps_the_stop_and_rejects_bad_levels() -> None:
    p = plan_long(cap=1.0)
    assert p.stop == pytest.approx(99.0)  # raw 98 is wider than the 1 % cap
    assert (p.tp1, p.tp2) == (101.5, 103.5)
    assert p.notional == 500 and p.qty == pytest.approx(5.0)
    assert fm.plan(  # stop on the wrong side of the fill
        "long", 100, 1, 101, 100, margin=50, leverage=10, stop_cap_pct=2,
        tp1_atr=1.5, tp2_atr=3.5, slippage_pct=0,
    ) is None  # fmt: skip


def test_stop_first_loses_the_whole_position() -> None:
    p = plan_long()
    st = state(p)
    out = run(st, [bar(0, 100, 101, 97.9, 98.5)])
    assert out is not None and out.reason == "stop" and out.price == pytest.approx(98.0)
    assert fm.settle(st).pnl == pytest.approx(-10.0)  # 5 units x 2.0
    assert fm.settle(st).r_multiple == pytest.approx(-1.0)


def test_tp1_partial_then_tp2() -> None:
    p = plan_long()
    st = state(p)
    assert run(st, [bar(0, 100, 101.6, 99.9, 101.2)]) is None
    assert st.tp1_done and st.remaining == pytest.approx(0.5)
    out = run(st, [bar(1, 101, 103.6, 101, 103)])
    assert out is not None and out.reason == "tp2"
    # half at +1.5, half at +3.5 on 5 units
    assert fm.settle(st).pnl == pytest.approx(5 * 0.5 * 1.5 + 5 * 0.5 * 3.5)


def test_break_even_after_a_15m_bar_reaches_tp1() -> None:
    p = plan_long()
    st = state(p)
    edge = {T0 + BAR: fm.Boundary(high=101.6, low=99.9, atr=1.0, trend_bull=True, trend_bear=False)}
    assert run(st, [bar(0, 100, 101.6, 99.9, 101.2)]) is None  # no 15m boundary: stop unchanged
    assert st.tp1_done and not st.be and st.stop == pytest.approx(98.0)
    st = state(p)
    assert run(st, [bar(0, 100, 101.6, 99.9, 101.2)], edge) is None
    assert st.be and st.stop == pytest.approx(100.1)  # entry + 0.1 ATR
    out = run(st, [bar(1, 101, 101, 100.0, 100.2)])
    assert out is not None and out.reason == "be"


def test_trend_flip_closes_at_the_next_open() -> None:
    p = plan_long()
    st = state(p)
    edge = {T0 + BAR: fm.Boundary(100.5, 99.5, 1.0, trend_bull=False, trend_bear=True)}
    assert run(st, [bar(0, 100, 100.5, 99.5, 100.2)], edge) is None
    assert st.flip_pending
    out = run(st, [bar(1, 100.3, 100.6, 100.0, 100.4)])
    assert out is not None and out.reason == "flip" and out.price == pytest.approx(100.3)
    assert out.time == T0 + BAR


def test_short_mirrors_long() -> None:
    p = fm.plan(
        "short", 100.0, 1.0, 102.0, 100.0, margin=50, leverage=10, stop_cap_pct=2,
        tp1_atr=1.5, tp2_atr=3.5, slippage_pct=0,
    )  # fmt: skip
    assert p is not None and (p.stop, p.tp1, p.tp2) == (102.0, 98.5, 96.5)
    st = state(p, "short")
    out = run(st, [bar(0, 100, 102.1, 99.9, 101)])
    assert out is not None and out.reason == "stop" and fm.settle(st).pnl == pytest.approx(-10.0)


def _bars(n: int, step: timedelta, drift: float) -> list[fs.Bar]:
    out = []
    for i in range(n):
        base = 100 + drift * i + 2 * math.sin(i / 5)
        out.append(fs.Bar(T0 - (n - i) * step, base, base + 1, base - 1, base + 0.3))
    return out


def test_signal_series_is_aligned_and_never_both_sides() -> None:
    b15, b1h, b4h = (
        _bars(400, fs.BAR_15M, 0.05),
        _bars(200, fs.BAR_1H, 0.2),
        _bars(100, fs.BAR_4H, 0.8),
    )
    sigs = fs.compute(b15, b1h, b4h, fs.StrategyParams(min_score=1, adx_min=1))
    assert len(sigs) == len(b15)
    assert sigs[0] is None  # indicators not ready on the first bars
    ready = [s for s in sigs if s is not None]
    assert ready and all(not (s.long and s.short) for s in ready)
    assert all(
        s.close_time == b.open_time + fs.BAR_15M for s, b in zip(sigs, b15, strict=True) if s
    )
    strict = fs.compute(b15, b1h, b4h, fs.StrategyParams(adx_min=1000))
    assert not any(s.long or s.short for s in strict if s)
