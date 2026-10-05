# Range Filter [DW] port (S / M / R engine, "Average Filter Changes" on).
#
# Original work: "Range Filter [DW]" by DonovanWall, licensed under the Mozilla Public License
# 2.0 (https://mozilla.org/MPL/2.0/). This file is a derivative Python port of that logic as
# used in agent-kit/reference/pine/fgi_replica_v3.pine and is made available under MPL-2.0.
"""Range filter: lineM / lineR / lineS and the M trend (Pine `trend` variable)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from tss.indicators.primitives import NAN, Series, ema, isnan


@dataclass(frozen=True)
class RangeFilterParams:
    kind: str = "Type 1"  # "Type 1" | "Type 2"
    movement: str = "Close"  # "Close" | "Wicks"
    qty: float = 2.618
    period: int = 14
    smooth: bool = True
    smooth_period: int = 27
    average: bool = True
    average_n: int = 2


@dataclass(frozen=True)
class RangeFilterResult:
    filt: Series
    line_m: Series
    line_r: Series
    line_s: Series
    trend: list[int]  # 1 up, -1 down, 0 not yet known
    moved: list[bool]


def cond_ema(values: Sequence[float], cond: Sequence[bool], n: int) -> Series:
    """Pine `condEma`: an EMA that only takes a new sample when `cond` is true."""
    out: Series = []
    e = NAN
    alpha = 2.0 / (n + 1)
    for x, c in zip(values, cond, strict=True):
        if c and not isnan(x):
            e = x if isnan(e) else e + (x - e) * alpha
        out.append(e)
    return out


def range_filter(
    high: Sequence[float],
    low: Sequence[float],
    close: Sequence[float],
    p: RangeFilterParams | None = None,
) -> RangeFilterResult:
    p = p or RangeFilterParams()
    n = len(close)
    rf_h = list(high) if p.movement == "Wicks" else list(close)
    rf_l = list(low) if p.movement == "Wicks" else list(close)
    rf_x = [(h + lo) / 2.0 for h, lo in zip(rf_h, rf_l, strict=True)]

    abs_change = [NAN] + [abs(rf_x[i] - rf_x[i - 1]) for i in range(1, n)]
    rf_ac = ema(abs_change, p.period)
    rf_rng = [p.qty * a for a in rf_ac]
    rf_r = ema(rf_rng, p.smooth_period) if p.smooth else rf_rng

    filt: Series = []
    state = NAN
    for i in range(n):
        prev = rf_x[i] if isnan(state) else state
        nxt = prev
        r = rf_r[i]
        if not isnan(r):
            if p.kind == "Type 1":
                if rf_h[i] - r > prev:
                    nxt = rf_h[i] - r
                if rf_l[i] + r < prev:
                    nxt = rf_l[i] + r
            else:
                if rf_h[i] >= prev + r:
                    nxt = prev + float(int(abs(rf_h[i] - prev) // r)) * r
                if rf_l[i] <= prev - r:
                    nxt = prev - float(int(abs(rf_l[i] - prev) // r)) * r
        state = nxt
        filt.append(state)

    moved = [True] + [filt[i] != filt[i - 1] for i in range(1, n)]
    if p.average:
        line_m = cond_ema(filt, moved, p.average_n)
        line_r = cond_ema([f + r for f, r in zip(filt, rf_r, strict=True)], moved, p.average_n)
        line_s = cond_ema([f - r for f, r in zip(filt, rf_r, strict=True)], moved, p.average_n)
    else:
        line_m = list(filt)
        line_r = [f + r for f, r in zip(filt, rf_r, strict=True)]
        line_s = [f - r for f, r in zip(filt, rf_r, strict=True)]

    trend: list[int] = []
    t = 0
    for i in range(n):
        if i > 0:
            if line_m[i] > line_m[i - 1]:
                t = 1
            elif line_m[i] < line_m[i - 1]:
                t = -1
        trend.append(t)
    return RangeFilterResult(filt, line_m, line_r, line_s, trend, moved)
