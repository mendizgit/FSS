"""Pine Script v6 built-ins re-implemented with Pine semantics (skills/pine-port.md).

All series are plain `list[float]` oldest -> newest. Missing values are NaN and propagate
(comparisons with NaN are false, as in Pine). Nothing here reads the clock or does I/O.

Semantics replicated:
- ta.ema / ta.rma: seeded with the SMA of the first `length` values; alpha = 2/(n+1) and 1/n.
- ta.rsi / ta.atr: built on rma. ta.stdev is the population (biased) deviation.
- ta.pivothigh/low(left, right): confirmed `right` bars later (never uses future bars).
  Assumption to confirm with the parity check: the centre must be strictly above (below) the
  `left` bars and at least as high (low) as the `right` bars.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import datetime

NAN = math.nan
Series = list[float]


def isnan(x: float) -> bool:
    return x != x


def nz(x: float, default: float = 0.0) -> float:
    return default if isnan(x) else x


def sma(src: Sequence[float], length: int) -> Series:
    """Window mean; NaN until a full window of non-NaN values exists."""
    out = [NAN] * len(src)
    for i in range(length - 1, len(src)):
        window = src[i - length + 1 : i + 1]
        if not any(isnan(v) for v in window):
            out[i] = math.fsum(window) / length
    return out


def _smoothed(src: Sequence[float], length: int, alpha: float) -> Series:
    """Shared body of ta.ema (alpha = 2/(n+1)) and ta.rma (alpha = 1/n)."""
    out = [NAN] * len(src)
    state = NAN
    for i, x in enumerate(src):
        if isnan(state):
            if i >= length - 1:
                window = src[i - length + 1 : i + 1]
                if not any(isnan(v) for v in window):
                    state = math.fsum(window) / length  # SMA seed
        elif isnan(x):
            state = NAN
        else:
            state = alpha * x + (1.0 - alpha) * state
        out[i] = state
    return out


def ema(src: Sequence[float], length: int) -> Series:
    return _smoothed(src, length, 2.0 / (length + 1))


def rma(src: Sequence[float], length: int) -> Series:
    return _smoothed(src, length, 1.0 / length)


def change(src: Sequence[float]) -> Series:
    return [NAN] + [src[i] - src[i - 1] for i in range(1, len(src))]


def rsi(src: Sequence[float], length: int) -> Series:
    """Wilder RSI as ta.rsi: 100 when there are no losses, 0 when there are no gains."""
    ch = change(src)
    up = rma([NAN if isnan(c) else max(c, 0.0) for c in ch], length)
    down = rma([NAN if isnan(c) else -min(c, 0.0) for c in ch], length)
    out = [NAN] * len(src)
    for i in range(len(src)):
        u, d = up[i], down[i]
        if isnan(u) or isnan(d):
            continue
        out[i] = 100.0 if d == 0 else 0.0 if u == 0 else 100.0 - 100.0 / (1.0 + u / d)
    return out


def true_range(high: Sequence[float], low: Sequence[float], close: Sequence[float]) -> Series:
    """ta.tr(true): the first bar is high - low (no previous close)."""
    out = [high[0] - low[0]] if high else []
    for i in range(1, len(high)):
        out.append(max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1])))
    return out


def atr(high: Sequence[float], low: Sequence[float], close: Sequence[float], length: int) -> Series:
    return rma(true_range(high, low, close), length)


def stdev(src: Sequence[float], length: int) -> Series:
    """Population (biased) standard deviation over the window."""
    out = [NAN] * len(src)
    for i in range(length - 1, len(src)):
        window = src[i - length + 1 : i + 1]
        if any(isnan(v) for v in window):
            continue
        mean = math.fsum(window) / length
        out[i] = math.sqrt(math.fsum((v - mean) ** 2 for v in window) / length)
    return out


def bollinger(src: Sequence[float], length: int, mult: float) -> tuple[Series, Series, Series]:
    """ta.bb: basis = sma, bands = basis +/- mult * population stdev. Returns (mid, up, down)."""
    mid = sma(src, length)
    dev = stdev(src, length)
    up = [
        m + mult * d if not (isnan(m) or isnan(d)) else NAN for m, d in zip(mid, dev, strict=True)
    ]
    dn = [
        m - mult * d if not (isnan(m) or isnan(d)) else NAN for m, d in zip(mid, dev, strict=True)
    ]
    return mid, up, dn


def highest(src: Sequence[float], length: int) -> Series:
    """Highest over the last `length` bars (NaN inside the window are ignored; NaN until a
    full window of bars exists)."""
    out = [NAN] * len(src)
    for i in range(length - 1, len(src)):
        vals = [v for v in src[i - length + 1 : i + 1] if not isnan(v)]
        if vals:
            out[i] = max(vals)
    return out


def lowest(src: Sequence[float], length: int) -> Series:
    out = [NAN] * len(src)
    for i in range(length - 1, len(src)):
        vals = [v for v in src[i - length + 1 : i + 1] if not isnan(v)]
        if vals:
            out[i] = min(vals)
    return out


def pivot_high(src: Sequence[float], left: int, right: int) -> Series:
    """Value of the pivot high, reported at the bar where it is confirmed (centre + right)."""
    out = [NAN] * len(src)
    for i in range(left + right, len(src)):
        c = i - right
        centre = src[c]
        if isnan(centre):
            continue
        ok = all(src[c - k] < centre for k in range(1, left + 1) if not isnan(src[c - k])) and all(
            src[c + k] <= centre for k in range(1, right + 1) if not isnan(src[c + k])
        )
        if ok:
            out[i] = centre
    return out


def pivot_low(src: Sequence[float], left: int, right: int) -> Series:
    out = [NAN] * len(src)
    for i in range(left + right, len(src)):
        c = i - right
        centre = src[c]
        if isnan(centre):
            continue
        ok = all(src[c - k] > centre for k in range(1, left + 1) if not isnan(src[c - k])) and all(
            src[c + k] >= centre for k in range(1, right + 1) if not isnan(src[c + k])
        )
        if ok:
            out[i] = centre
    return out


def vwap_daily(
    open_times: Sequence[datetime],
    price: Sequence[float],
    volume: Sequence[float],
) -> Series:
    """ta.vwap(hlc3) anchored to the UTC day (crypto sessions run 00:00-24:00 UTC).

    Cumulative sum(price * volume) / sum(volume), reset on each new UTC date. NaN while the
    cumulative volume is zero or missing.
    """
    out = [NAN] * len(price)
    day = None
    pv = vol = 0.0
    for i, t in enumerate(open_times):
        if t.date() != day:
            day = t.date()
            pv = vol = 0.0
        if not isnan(price[i]) and not isnan(volume[i]):
            pv += price[i] * volume[i]
            vol += volume[i]
        out[i] = pv / vol if vol > 0 else NAN
    return out


def at(series: Sequence[float], i: int, back: int = 0) -> float:
    """series[i - back] with NaN before the start (Pine's x[n])."""
    j = i - back
    return series[j] if 0 <= j < len(series) else NAN


def sar(
    high: Sequence[float],
    low: Sequence[float],
    close: Sequence[float],
    start: float,
    inc: float,
    maximum: float,
) -> Series:
    """ta.sar(start, inc, max), following the reference implementation in the Pine docs.

    Path dependent: the first bar fixes the initial trend from close[1] vs close[0]. Output is
    NaN on the first bar (Pine returns na there).
    """
    n = len(close)
    out = [NAN] * n
    result = max_min = accel = NAN
    is_below = False
    for i in range(1, n):
        first_trend_bar = False
        if i == 1:
            if close[1] > close[0]:
                is_below, max_min, result = True, high[1], low[0]
            else:
                is_below, max_min, result = False, low[1], high[0]
            first_trend_bar = True
            accel = start
        result = result + accel * (max_min - result)
        if is_below:
            if result > low[i]:
                first_trend_bar = True
                is_below = False
                result = max(high[i], max_min)
                max_min = low[i]
                accel = start
        elif result < high[i]:
            first_trend_bar = True
            is_below = True
            result = min(low[i], max_min)
            max_min = high[i]
            accel = start
        if not first_trend_bar:
            if is_below:
                if high[i] > max_min:
                    max_min = high[i]
                    accel = min(accel + inc, maximum)
            elif low[i] < max_min:
                max_min = low[i]
                accel = min(accel + inc, maximum)
        if is_below:
            result = min(result, low[i - 1])
            if i > 1:
                result = min(result, low[i - 2])
        else:
            result = max(result, high[i - 1])
            if i > 1:
                result = max(result, high[i - 2])
        out[i] = result
    return out


def stoch(src: Sequence[float], length: int) -> Series:
    """ta.stoch(src, src, src, length): 100 * (src - lowest) / (highest - lowest); NaN when the
    window is flat (Pine divides by zero)."""
    hi = highest(src, length)
    lo = lowest(src, length)
    out = [NAN] * len(src)
    for i in range(len(src)):
        rng = hi[i] - lo[i]
        if not (isnan(rng) or isnan(src[i])) and rng != 0:
            out[i] = 100.0 * (src[i] - lo[i]) / rng
    return out


def stoch_rsi(
    close: Sequence[float], rsi_len: int, stoch_len: int, k_smooth: int, d_smooth: int
) -> tuple[Series, Series]:
    """StochRSI as the Pine script builds it: k = sma(stoch(rsi), kSm), d = sma(k, dSm)."""
    r = rsi(close, rsi_len)
    k = sma(stoch(r, stoch_len), k_smooth)
    return k, sma(k, d_smooth)
