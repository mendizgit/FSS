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
