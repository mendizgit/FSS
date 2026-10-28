"""FGI Pro Strategy v2.0 (15m) entry signals (pure).

Port of agent-kit/reference/pine/strategy build on FGI.txt, as replayed in the backtests:
6-factor confluence (higher-timeframe SuperTrend, local SuperTrend, 1H + 4H RSI, support /
resistance or EMA32 proximity, RSI divergence, sweep reversal), ADX gate, and ATR / swing levels.
The higher-timeframe trend is the 1H SuperTrend; with `use_4h` the 4H SuperTrend is the trend and
the 1H SuperTrend must agree as well. Only closed bars are used and every higher-timeframe value
comes from the last bar closed at or before the signal bar's close (no lookahead).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import NamedTuple

from tss.indicators.fgi_v3 import align
from tss.indicators.primitives import (
    atr,
    bollinger,
    ema,
    isnan,
    pivot_high,
    pivot_low,
    rma,
    rsi,
    true_range,
)
from tss.indicators.supertrend import supertrend

NAN = math.nan
BAR_15M = timedelta(minutes=15)
BAR_1H = timedelta(hours=1)
BAR_4H = timedelta(hours=4)
PIVOT = 7  # swing pivot width (bars each side)
DIV_PIVOT = 3  # RSI pivot width
SWEEP_BARS = 5
DIV_BARS = 20
MIN_BARS_15M = 120  # warm-up for ATR, ADX, EMA32 and the pivots
MIN_BARS_HTF = 40


class Bar(NamedTuple):
    open_time: datetime
    open: float
    high: float
    low: float
    close: float


@dataclass(frozen=True)
class StrategyParams:
    min_score: int = 4  # factors needed out of 6
    adx_min: float = 35.0
    use_4h: bool = False  # False: trend = 1H SuperTrend. True: trend = 4H SuperTrend and 1H agrees


@dataclass(frozen=True)
class Signal:
    """One evaluated 15m bar (a bar whose indicators are not ready is None in the series)."""

    close_time: datetime
    close: float
    atr: float
    adx: float
    long: bool
    short: bool
    long_score: int
    short_score: int
    long_stop: float  # swing / ATR stop before the percentage cap
    short_stop: float
    trend_bull: bool  # the higher-timeframe trend in effect
    trend_bear: bool


def dmi_adx(high: list[float], low: list[float], close: list[float], n: int = 14) -> list[float]:
    """Wilder ADX (RMA of DX)."""
    size = len(close)
    plus = [NAN] * size
    minus = [NAN] * size
    for i in range(1, size):
        up, down = high[i] - high[i - 1], low[i - 1] - low[i]
        plus[i] = up if (up > down and up > 0) else 0.0
        minus[i] = down if (down > up and down > 0) else 0.0
    rng = rma(true_range(high, low, close), n)
    p, m = rma(plus, n), rma(minus, n)
    dx: list[float] = []
    for i in range(size):
        if isnan(rng[i]) or isnan(p[i]) or isnan(m[i]) or rng[i] == 0:
            dx.append(NAN)
            continue
        pl, mi = 100 * p[i] / rng[i], 100 * m[i] / rng[i]
        total = pl + mi
        dx.append(abs(pl - mi) / (total if total != 0 else 1))
    return [100 * v if not isnan(v) else v for v in rma(dx, n)]


def _direction(bars: list[Bar], length: int = 10, mult: float = 3.0) -> list[float]:
    """SuperTrend direction (-1 bull, 1 bear, NaN while the ATR is not ready)."""
    high = [b.high for b in bars]
    low = [b.low for b in bars]
    close = [b.close for b in bars]
    _, direction = supertrend(high, low, close, mult, length)
    ready = atr(high, low, close, length)
    return [float(d) if not isnan(a) else NAN for d, a in zip(direction, ready, strict=True)]


def compute(
    b15: list[Bar], b1h: list[Bar], b4h: list[Bar], params: StrategyParams | None = None
) -> list[Signal | None]:
    """Signal series, index-aligned with `b15` (oldest first, closed bars only)."""
    p = params or StrategyParams()
    o = [b.open for b in b15]
    h = [b.high for b in b15]
    lo = [b.low for b in b15]
    c = [b.close for b in b15]
    n = len(c)
    close_time = [b.open_time + BAR_15M for b in b15]
    a = atr(h, lo, c, 14)
    _, local_dir = supertrend(h, lo, c, 3.0, 10)
    dir_4h = align(close_time, [b.open_time for b in b4h], BAR_4H, _direction(b4h))
    dir_1h = align(close_time, [b.open_time for b in b1h], BAR_1H, _direction(b1h))
    rsi_1h = align(close_time, [b.open_time for b in b1h], BAR_1H, rsi([b.close for b in b1h], 14))
    rsi_4h = align(close_time, [b.open_time for b in b4h], BAR_4H, rsi([b.close for b in b4h], 14))
    e32 = ema(c, 32)
    _, bb_up, bb_dn = bollinger(c, 20, 2.0)
    adx = dmi_adx(h, lo, c)
    rs = rsi(c, 14)
    ph, pl = pivot_high(h, PIVOT, PIVOT), pivot_low(lo, PIVOT, PIVOT)
    dph, dpl = pivot_high(rs, DIV_PIVOT, DIV_PIVOT), pivot_low(rs, DIV_PIVOT, DIV_PIVOT)

    last_sh = last_sl = NAN
    sweep_bull_at = sweep_bear_at = div_bull_at = div_bear_at = 0
    sweep_bull = sweep_bear = div_bull = div_bear = False
    p_rh = p_ph = c_rh = c_ph = p_rl = p_pl = c_rl = c_pl = NAN
    out: list[Signal | None] = []
    for i in range(n):
        if not isnan(ph[i]):
            last_sh = h[i - PIVOT]
        if not isnan(pl[i]):
            last_sl = lo[i - PIVOT]
        if i > 0:
            if lo[i] < lo[i - 1] and c[i] > h[i - 1] and c[i] > o[i]:
                sweep_bull, sweep_bull_at = True, i
            if h[i] > h[i - 1] and c[i] < lo[i - 1] and c[i] < o[i]:
                sweep_bear, sweep_bear_at = True, i
        if i - sweep_bull_at > SWEEP_BARS:
            sweep_bull = False
        if i - sweep_bear_at > SWEEP_BARS:
            sweep_bear = False
        if not isnan(dph[i]):
            p_rh, p_ph, c_rh, c_ph = c_rh, c_ph, rs[i - DIV_PIVOT], h[i - DIV_PIVOT]
        if not isnan(dpl[i]):
            p_rl, p_pl, c_rl, c_pl = c_rl, c_pl, rs[i - DIV_PIVOT], lo[i - DIV_PIVOT]
        bull = not isnan(p_rl) and not isnan(c_rl) and c_pl < p_pl and c_rl > p_rl and c_rl < 50
        bear = not isnan(p_rh) and not isnan(c_rh) and c_ph > p_ph and c_rh < p_rh and c_rh > 50
        if bull:
            div_bull, div_bull_at = True, i
        if bear:
            div_bear, div_bear_at = True, i
        if i - div_bull_at > DIV_BARS:
            div_bull = False
        if i - div_bear_at > DIV_BARS:
            div_bear = False

        trend_dir = dir_4h[i] if p.use_4h else dir_1h[i]
        needed = (a[i], trend_dir, dir_1h[i], rsi_1h[i], rsi_4h[i], e32[i], bb_up[i], adx[i])
        if any(isnan(v) for v in needed) or local_dir[i] == 0:
            out.append(None)
            continue
        trend_bull, trend_bear = trend_dir < 0, trend_dir > 0
        loc_bull, loc_bear = local_dir[i] < 0, local_dir[i] > 0
        at_support = lo[i] <= bb_dn[i] or (
            not isnan(last_sl) and lo[i] <= last_sl + a[i] * 0.8 and c[i] >= last_sl - a[i] * 0.5
        )
        at_resist = h[i] >= bb_up[i] or (
            not isnan(last_sh) and h[i] >= last_sh - a[i] * 0.8 and c[i] <= last_sh + a[i] * 0.5
        )
        near_ema = abs(c[i] - e32[i]) <= a[i] * 0.6
        long_score = sum(
            [
                trend_bull,
                loc_bull,
                rsi_1h[i] > 45 and rsi_4h[i] > 45,
                at_support or near_ema,
                div_bull,
                sweep_bull,
            ]
        )
        short_score = sum(
            [
                trend_bear,
                loc_bear,
                rsi_1h[i] < 55 and rsi_4h[i] < 55,
                at_resist or near_ema,
                div_bear,
                sweep_bear,
            ]
        )
        strong = adx[i] >= p.adx_min
        agree_bull = (not p.use_4h) or dir_1h[i] < 0
        agree_bear = (not p.use_4h) or dir_1h[i] > 0
        long_ok = long_score >= p.min_score and trend_bull and loc_bull and strong and agree_bull
        short_ok = short_score >= p.min_score and trend_bear and loc_bear and strong and agree_bear
        long_stop = (
            min(last_sl - a[i] * 0.2, c[i] - a[i] * 1.5)
            if not isnan(last_sl)
            else c[i] - a[i] * 1.5
        )
        short_stop = (
            max(last_sh + a[i] * 0.2, c[i] + a[i] * 1.5)
            if not isnan(last_sh)
            else c[i] + a[i] * 1.5
        )
        out.append(
            Signal(
                close_time=close_time[i],
                close=c[i],
                atr=a[i],
                adx=adx[i],
                long=long_ok,
                short=short_ok,
                long_score=long_score,
                short_score=short_score,
                long_stop=long_stop,
                short_stop=short_stop,
                trend_bull=trend_bull,
                trend_bear=trend_bear,
            )
        )
    return out
