"""ta.supertrend(factor, atrPeriod) with Pine's band-ratcheting rule.

Direction follows Pine's sign convention: -1 = bullish (price above the line), 1 = bearish.
"""

from __future__ import annotations

from collections.abc import Sequence

from tss.indicators.primitives import NAN, Series, atr, isnan, nz


def supertrend(
    high: Sequence[float],
    low: Sequence[float],
    close: Sequence[float],
    factor: float,
    atr_length: int,
) -> tuple[Series, list[int]]:
    """Returns (supertrend line, direction) per bar."""
    n = len(close)
    a = atr(high, low, close, atr_length)
    upper = [NAN] * n
    lower = [NAN] * n
    line = [NAN] * n
    direction = [1] * n
    for i in range(n):
        src = (high[i] + low[i]) / 2.0
        ub = src + factor * a[i]
        lb = src - factor * a[i]
        prev_lb = nz(lower[i - 1]) if i > 0 else 0.0
        prev_ub = nz(upper[i - 1]) if i > 0 else 0.0
        prev_close = close[i - 1] if i > 0 else NAN
        lb = lb if (lb > prev_lb or prev_close < prev_lb) else prev_lb
        ub = ub if (ub < prev_ub or prev_close > prev_ub) else prev_ub
        lower[i], upper[i] = lb, ub
        prev_st = line[i - 1] if i > 0 else NAN
        if i == 0 or isnan(a[i - 1]):
            d = 1
        elif prev_st == prev_ub:
            d = -1 if close[i] > ub else 1
        else:
            d = 1 if close[i] < lb else -1
        direction[i] = d
        line[i] = lb if d == -1 else ub
    return line, direction
