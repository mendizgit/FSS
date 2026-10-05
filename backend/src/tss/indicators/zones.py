"""Extreme zones (approximation of FGI COM's orange / green clouds), as in the Pine script.

The centre (zC) and half-width (zB) step only when the S / M / R filter moves, using the
PREVIOUS bar's SMA(hl2) and stdev(hlc3).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from tss.indicators.primitives import NAN, Series, isnan


@dataclass(frozen=True)
class ZoneParams:
    ma_len: int = 190
    sd_len: int = 200
    mult: float = 3.0
    bias: float = 0.11
    inner: float = 0.764  # sub zone inner edge (x outer half-width)
    main_in: float = 0.667
    main_out: float = 1.4


def _window_stats(values: Sequence[float], end: int, length: int) -> tuple[float, float]:
    """(mean, population stdev) of values[end-length+1 : end+1]; NaN if incomplete or missing."""
    if end < length - 1:
        return NAN, NAN
    window = values[end - length + 1 : end + 1]
    if any(isnan(v) for v in window):
        return NAN, NAN
    mean = math.fsum(window) / length
    return mean, math.sqrt(math.fsum((v - mean) ** 2 for v in window) / length)


def zones(
    high: Sequence[float],
    low: Sequence[float],
    close: Sequence[float],
    moved: Sequence[bool],
    p: ZoneParams | None = None,
) -> tuple[Series, Series]:
    """Returns (zC, zB) per bar; NaN until the filter has moved with valid inputs.

    The window statistics are only evaluated where the filter moved (they are only read there).
    """
    p = p or ZoneParams()
    hl2 = [(h + lo) / 2.0 for h, lo in zip(high, low, strict=True)]
    hlc3 = [(h + lo + c) / 3.0 for h, lo, c in zip(high, low, close, strict=True)]
    zc: Series = []
    zb: Series = []
    c_state = b_state = NAN
    for i in range(len(close)):
        if i > 0 and moved[i]:
            ma = _window_stats(hl2, i - 1, p.ma_len)[0]
            sd = _window_stats(hlc3, i - 1, p.sd_len)[1]
            if not isnan(ma) and not isnan(sd):
                b_state = p.mult * sd
                c_state = ma + p.bias * b_state
        zc.append(c_state)
        zb.append(b_state)
    return zc, zb


def zone_position(close: float, zc: float, zb: float, p: ZoneParams | None = None) -> str | None:
    """Where the close sits relative to the zones. None while the zones are not defined.

    TOP_SUB / BOTTOM_SUB: inside or beyond the sub zone (>= inner edge, the most extreme).
    TOP_MAIN / BOTTOM_MAIN: inside the main zone (>= its inner edge) but short of the sub zone.
    MID: otherwise.
    """
    p = p or ZoneParams()
    if isnan(zc) or isnan(zb) or isnan(close):
        return None
    if close >= zc + p.inner * zb:
        return "TOP_SUB"
    if close >= zc + p.main_in * zb:
        return "TOP_MAIN"
    if close <= zc - p.inner * zb:
        return "BOTTOM_SUB"
    if close <= zc - p.main_in * zb:
        return "BOTTOM_MAIN"
    return "MID"
