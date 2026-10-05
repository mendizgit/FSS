"""Hand-computed checks for supertrend, range filter, zones, divergence and the composed FGI."""

import math
import random
from datetime import UTC, datetime, timedelta

import pytest

from tss.indicators.divergence import DivergenceEngine, DivParams, single_pivot_divergence
from tss.indicators.fgi_v3 import (
    Bars,
    FgiParams,
    HtfContext,
    against_htf,
    align,
    compute,
    event_at,
    recent_events,
    snapshot,
)
from tss.indicators.primitives import isnan
from tss.indicators.range_filter import RangeFilterParams, cond_ema, range_filter
from tss.indicators.supertrend import supertrend
from tss.indicators.zones import ZoneParams, zone_position, zones

NAN = math.nan
T0 = datetime(2026, 1, 1, tzinfo=UTC)


def test_supertrend_hand_computed() -> None:
    high = [11, 12, 14, 16, 17, 15]
    low = [9, 10, 11, 13, 14, 11]
    close = [10, 11, 13, 15, 14.5, 11.5]
    line, direction = supertrend(high, low, close, 1.0, 1)  # ATR(1) = true range
    assert direction == [1, 1, 1, -1, -1, 1]  # -1 = bullish (Pine convention)
    assert line == pytest.approx([0.0, 13.0, 13.0, 11.5, 12.5, 17.0])  # bar 0: Pine's nz() quirk


def test_cond_ema_only_samples_when_condition_holds() -> None:
    out = cond_ema([1, 2, 3, 4], [True, False, True, True], 2)  # alpha = 2/3
    assert out == pytest.approx([1.0, 1.0, 1 + 2 * 2 / 3, (1 + 4 / 3) + (4 - (1 + 4 / 3)) * 2 / 3])


def test_range_filter_type1_hand_computed() -> None:
    close = [10.0, 12.0, 12.0, 9.0]
    p = RangeFilterParams(qty=1.0, period=1, smooth=False, average=False)
    res = range_filter(close, close, close, p)
    assert res.filt == pytest.approx([10, 10, 12, 12])
    assert res.moved == [True, False, True, False]
    assert res.trend == [0, 0, 1, 1]  # M turns up when the filter moves up, holds when flat
    assert isnan(res.line_r[0]) and res.line_r[1:] == pytest.approx([12, 12, 15])
    assert res.line_s[1:] == pytest.approx([8, 12, 9])


def test_range_filter_flips_trend_both_ways() -> None:
    close = [100.0 + i for i in range(30)] + [130.0 - 2 * i for i in range(30)]
    res = range_filter(
        close, close, close, RangeFilterParams(qty=1.0, period=3, smooth=False, average=False)
    )
    assert 1 in res.trend and -1 in res.trend
    assert res.trend[29] == 1 and res.trend[-1] == -1


def test_zones_step_only_when_filter_moves_using_previous_bar() -> None:
    n = 12
    high = [10.0 + i for i in range(n)]
    low = [8.0 + i for i in range(n)]
    close = [9.0 + i for i in range(n)]
    moved = [True, False, True] + [False] * (n - 3)
    p = ZoneParams(ma_len=2, sd_len=2, mult=3.0, bias=0.1)
    zc, zb = zones(high, low, close, moved, p)
    assert isnan(zc[0]) and isnan(zc[1])  # no valid previous-bar stats yet at bar 0, no move at 1
    # at bar 2 (moved): previous bar (1) hl2 values are 9, 10 -> sma(2) = 9.5
    # hlc3 at bars 0,1 = 9, 10 -> population stdev = 0.5 -> zB = 1.5, zC = 9.5 + 0.1 * 1.5
    assert zb[2] == pytest.approx(1.5) and zc[2] == pytest.approx(9.65)
    assert zc[3:] == pytest.approx([9.65] * (n - 3))  # held while the filter does not move


def test_zone_position_labels() -> None:
    p = ZoneParams()
    assert zone_position(100, 100, 10, p) == "MID"
    assert zone_position(107.7, 100, 10, p) == "TOP_SUB"  # >= 100 + 0.764 * 10
    assert zone_position(107.0, 100, 10, p) == "TOP_MAIN"  # >= 100 + 0.667 * 10
    assert zone_position(92.2, 100, 10, p) == "BOTTOM_SUB"
    assert zone_position(93.0, 100, 10, p) == "BOTTOM_MAIN"
    assert zone_position(100, NAN, 10, p) is None


def test_align_uses_only_closed_htf_bars() -> None:
    h = timedelta(hours=1)
    htf_open = [T0, T0 + h, T0 + 2 * h]
    values = [10.0, 20.0, 30.0]
    # signal bars close at 00:30, 01:00, 01:30, 02:00
    closes = [T0 + timedelta(minutes=30 * k) for k in range(1, 5)]
    out = align(closes, htf_open, h, values)
    assert isnan(out[0])  # the 00:00 HTF bar is still forming at 00:30
    assert out[1:] == [10.0, 10.0, 20.0]  # 01:00 -> first bar closed; 02:00 -> second closed


def test_single_pivot_divergence_persists_then_decays() -> None:
    # RSI lows 20 (price low 7) then 25 (price low 6): lower price low, higher RSI low, RSI < 50
    rsi_vals = [50, 40, 30, 20, 30, 40, 50, 40, 30, 25, 30, 40, 50]
    low = [10, 9, 8, 7, 8, 9, 10, 9, 8, 6, 8, 9, 10]
    # a third RSI low (22) with a lower price low (5) breaks the pattern (RSI low no longer higher)
    rsi_vals += [45, 35, 22, 35, 45, 50] + [50.0] * 20
    low += [9, 8, 5, 8, 9, 10] + [10.0] * 20
    high = [x + 1 for x in low]
    bull, bear = single_pivot_divergence(rsi_vals, high, low, length=3, sticky=5)
    assert bull.index(True) == 12  # second RSI pivot (index 9) is confirmed 3 bars later
    assert not any(bear)
    # the condition is a state: the flag stays on every bar while it holds (indices 12..17) ...
    assert bull[12:18] == [True] * 6
    # ... the third pivot (confirmed at 18) breaks it, then the flag lasts `sticky` more bars
    assert bull[18:23] == [True] * 5 and not bull[23]


def test_divergence_engine_regular_positive() -> None:
    # price lower low, RSI higher low, with a clean line of sight between the two lows
    close = [20, 19, 18, 17, 16, 15, 16, 17, 18, 17, 16, 15, 14.5, 15, 16, 17]
    rsi = [60, 55, 50, 45, 40, 30, 38, 46, 52, 46, 40, 34, 31, 36, 42, 48]
    eng = DivergenceEngine(rsi, close, close, close, DivParams(pivot_period=2, max_bars=100))
    found = [i for i in range(len(close)) if eng.detect(i).pos_reg > 0]
    assert found, "expected a regular bullish divergence"
    assert eng.detect(len(close) - 1).neg_reg == 0


def _bars(n: int, seed: int, minutes: int = 5) -> Bars:
    rng = random.Random(seed)
    price = 100.0
    times, o, h, lo, c, v = [], [], [], [], [], []
    for i in range(n):
        drift = 0.04 * math.sin(i / 17.0)
        step = rng.gauss(drift, 0.6)
        op = price
        price = max(price + step, 1.0)
        hi = max(op, price) + abs(rng.gauss(0, 0.3))
        low = min(op, price) - abs(rng.gauss(0, 0.3))
        times.append(T0 + timedelta(minutes=minutes * i))
        o.append(op)
        h.append(hi)
        lo.append(low)
        c.append(price)
        v.append(10 + rng.random())
    return Bars(times, o, h, lo, c, v)


def _htf(n: int) -> HtfContext:
    return HtfContext([-1] * n, [60.0] * n, [60.0] * n)


def test_compute_is_causal_and_deterministic() -> None:
    """Bars after k must never change anything at or before k (no lookahead)."""
    bars = _bars(420, seed=7)
    full = compute(bars, _htf(len(bars)))
    again = compute(bars, _htf(len(bars)))
    assert full.line_m == again.line_m or all(
        (isnan(a) and isnan(b)) or a == b for a, b in zip(full.line_m, again.line_m, strict=True)
    )
    for k in (150, 260, 330):
        part = Bars(
            *(
                x[: k + 1]
                for x in (bars.open_time, bars.open, bars.high, bars.low, bars.close, bars.volume)
            )
        )
        cut = compute(part, _htf(len(part)))
        for name in (
            "trend",
            "bull_t",
            "bear_t",
            "buy",
            "sell",
            "td_bull",
            "td_bear",
            "r_letter",
            "s_letter",
            "long_score",
            "short_score",
            "ct_buy_count",
            "ct_sell_count",
        ):
            assert getattr(cut, name)[k] == getattr(full, name)[k], (name, k)
        for name in ("line_m", "line_r", "line_s", "ema1", "ema3", "rsi", "zone_c", "vwap"):
            a, b = getattr(cut, name)[k], getattr(full, name)[k]
            assert (isnan(a) and isnan(b)) or a == pytest.approx(b, rel=1e-12), (name, k)


def test_buy_sell_only_fire_on_flips_and_buy_needs_the_rsi_gate() -> None:
    bars = _bars(900, seed=11)
    s = compute(bars, _htf(len(bars)))
    assert any(s.bull_t) and any(s.bear_t)
    for i in range(len(bars)):
        if s.buy[i]:
            assert s.bull_t[i] and min(s.rsi[max(0, i - 20) : i + 1]) <= 30.0
        if s.sell[i]:
            assert s.bear_t[i] and max(s.rsi[max(0, i - 20) : i + 1]) >= 70.0
        assert not (s.bull_t[i] and s.bear_t[i])
    no_gate = compute(bars, _htf(len(bars)), FgiParams(use_gate=False))
    assert no_gate.buy == no_gate.bull_t and no_gate.sell == no_gate.bear_t
    assert sum(s.buy) <= sum(s.bull_t)


def test_event_priority_and_against_htf() -> None:
    bars = _bars(900, seed=11)
    s = compute(bars, _htf(len(bars)))
    i = next(i for i in range(len(bars)) if s.buy[i])
    assert event_at(s, i) == "BUY"  # BUY outranks the bullT it contains
    assert against_htf(s, i, "BUY") is False  # HTF context is bullish in this fixture
    s.htf_dir[i] = 1
    assert against_htf(s, i, "BUY") is True
    s.htf_dir[i] = 0
    assert against_htf(s, i, "BUY") is True  # unknown HTF is not "with" the trend
    assert against_htf(s, i, "TD_BULL") is None


def test_snapshot_values_are_consistent() -> None:
    bars = _bars(700, seed=5)
    s = compute(bars, _htf(len(bars)))
    snap = snapshot(bars, s, timedelta(minutes=5))
    assert snap.bar_close_time == bars.open_time[-1] + timedelta(minutes=5)
    assert snap.m_trend in ("UP", "DOWN")
    assert snap.last_event in ("BUY", "SELL", "BULL_T", "BEAR_T", "TD_BULL", "TD_BEAR", "NONE")
    assert (snap.last_event == "NONE") == (snap.bars_ago is None)
    assert snap.price_vs_vwap in ("ABOVE", "BELOW")
    events = recent_events(bars, s, timedelta(minutes=5), 700)
    if events:
        last_time, last_event, _ = events[-1]
        assert (
            (last_event == snap.last_event)
            or snap.bars_ago == 0
            or last_time <= snap.bar_close_time
        )
