"""Shared pure calculations (Arch §5). No I/O, no clock reads."""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from datetime import datetime, timedelta
from enum import StrEnum
from itertools import pairwise

BAR = timedelta(minutes=15)


class Direction(StrEnum):
    RISING = "RISING"
    FALLING = "FALLING"
    FLAT = "FLAT"


def pct_change(now: float | None, then: float | None) -> float | None:
    """((now / then) - 1) * 100; None if either is missing or `then` <= 0."""
    if now is None or then is None or then <= 0:
        return None
    return (now / then - 1.0) * 100.0


def direction(change: float | None, deadband: float) -> Direction | None:
    """RISING if change > +deadband, FALLING if < -deadband, else FLAT. None if no change."""
    if change is None:
        return None
    if change > deadband:
        return Direction.RISING
    if change < -deadband:
        return Direction.FALLING
    return Direction.FLAT


def is_closed(open_time: datetime, now: datetime) -> bool:
    """A 15m bar is closed when open_time + 15 min <= now."""
    return open_time + BAR <= now


def rvol(amounts: Sequence[float | None], lookback: int) -> float | None:
    """amount[last] / median(amount of the `lookback` bars before it).

    `amounts` is oldest -> newest closed bars. None if fewer than lookback+1 bars, any needed
    value is missing, or the median is 0.
    """
    if len(amounts) < lookback + 1:
        return None
    window = amounts[-(lookback + 1) :]
    if any(a is None for a in window):
        return None
    values = [float(a) for a in window if a is not None]
    median = statistics.median(values[:-1])
    if median == 0:
        return None
    return values[-1] / median


def window_sum_change(values: Sequence[float | None], n: int) -> float | None:
    """pct change of sum(last n) vs sum(previous n). Needs 2n values, none missing."""
    if len(values) < 2 * n:
        return None
    window = values[-2 * n :]
    if any(v is None for v in window):
        return None
    nums = [float(v) for v in window if v is not None]
    return pct_change(sum(nums[n:]), sum(nums[:n]))


def window_price_change(closes: Sequence[float | None], n: int) -> float | None:
    """close[last] vs close[last - n]. Needs n+1 closes."""
    if len(closes) < n + 1:
        return None
    return pct_change(closes[-1], closes[-(n + 1)])


def has_gap(open_times: Sequence[datetime], needed: int) -> bool:
    """True if the newest `needed` bars are not strictly consecutive 15m bars, or too few exist."""
    if len(open_times) < needed:
        return True
    tail = open_times[-needed:]
    return any(b - a != BAR for a, b in pairwise(tail))


def nearest_within[T](
    items: Sequence[tuple[datetime, T]], target: datetime, tolerance_s: float
) -> T | None:
    """Value nearest to target within tolerance, else None (never interpolate)."""
    best: tuple[float, T] | None = None
    for ts, value in items:
        gap = abs((ts - target).total_seconds())
        if gap <= tolerance_s and (best is None or gap < best[0]):
            best = (gap, value)
    return None if best is None else best[1]
