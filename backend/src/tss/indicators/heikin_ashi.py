"""Heikin-Ashi transform (pure). Volume and open_time are carried over unchanged.

ha_close = (o+h+l+c)/4 · ha_open = (prev ha_open + prev ha_close)/2 (first bar: (o+c)/2) ·
ha_high = max(h, ha_open, ha_close) · ha_low = min(l, ha_open, ha_close).
ha_open is recursive, so always transform the full series (oldest first).
"""

from __future__ import annotations

from tss.indicators.fgi_v3 import Bars


def heikin_ashi(bars: Bars) -> Bars:
    n = len(bars)
    ha_o: list[float] = []
    ha_c: list[float] = []
    ha_h: list[float] = []
    ha_l: list[float] = []
    for i in range(n):
        o, h, lo, c = bars.open[i], bars.high[i], bars.low[i], bars.close[i]
        close = (o + h + lo + c) / 4.0
        open_ = (o + c) / 2.0 if i == 0 else (ha_o[i - 1] + ha_c[i - 1]) / 2.0
        ha_o.append(open_)
        ha_c.append(close)
        ha_h.append(max(h, open_, close))
        ha_l.append(min(lo, open_, close))
    return Bars(
        open_time=list(bars.open_time),
        open=ha_o,
        high=ha_h,
        low=ha_l,
        close=ha_c,
        volume=list(bars.volume),
    )
