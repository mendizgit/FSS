# RSI divergence engine: port (RSI only) of "Divergence for Many Indicators v4" by
# LonesomeTheBlue, licensed under the Mozilla Public License 2.0
# (https://mozilla.org/MPL/2.0/). This file is a derivative Python port of that logic as used
# in agent-kit/reference/pine/fgi_replica_v3.pine and is made available under MPL-2.0.
# Drawing (lines, labels) is out of scope; only the detection is ported.
"""Two divergence engines used by the FGI Replica V3 script.

1. `DivergenceEngine`: the multi-pivot regular / hidden divergence (LonesomeTheBlue). Pivot
   arrays are built sequentially; `detect(i)` evaluates one bar, so production only pays for
   the newest bar while the parity check can evaluate every bar.
2. `single_pivot_divergence`: the single-previous-pivot RSI divergence (sticky 20 bars) that
   feeds confluence factor 5.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from tss.indicators.primitives import NAN, isnan, nz, pivot_high, pivot_low


@dataclass(frozen=True)
class DivParams:
    pivot_period: int = 5
    source: str = "Close"  # "Close" | "High/Low"
    max_pivots: int = 10
    max_bars: int = 100
    no_confirm: bool = False


@dataclass(frozen=True)
class DivResult:
    pos_reg: int = 0
    neg_reg: int = 0
    pos_hid: int = 0
    neg_hid: int = 0

    def label(self, hidden: bool = False) -> str | None:
        """Newest type found, in Pine's order (the last non-zero of pos-reg, neg-reg, pos-hid,
        neg-hid wins). Regular divergences only unless `hidden` is true."""
        found = None
        for name, dist in (
            ("POS_REG", self.pos_reg),
            ("NEG_REG", self.neg_reg),
            *((("POS_HID", self.pos_hid), ("NEG_HID", self.neg_hid)) if hidden else ()),
        ):
            if dist > 0:
                found = name
        return found


@dataclass
class DivergenceEngine:
    rsi: Sequence[float]
    close: Sequence[float]
    high: Sequence[float]
    low: Sequence[float]
    params: DivParams = field(default_factory=DivParams)

    def __post_init__(self) -> None:
        p = self.params
        src_h = self.close if p.source == "Close" else self.high
        src_l = self.close if p.source == "Close" else self.low
        self._ph = pivot_high(src_h, p.pivot_period, p.pivot_period)
        self._pl = pivot_low(src_l, p.pivot_period, p.pivot_period)
        self._prsc_low = self.close if p.source == "Close" else self.low
        self._prsc_high = self.close if p.source == "Close" else self.high
        self._n = len(self.close)

    def _pivots_upto(self, i: int) -> tuple[list[tuple[int, float]], list[tuple[int, float]]]:
        """(highs, lows) as (confirmation bar index, value), newest first, at most 20 kept."""
        highs: list[tuple[int, float]] = []
        lows: list[tuple[int, float]] = []
        for j in range(i + 1):
            if not isnan(self._ph[j]):
                highs.insert(0, (j, self._ph[j]))
                del highs[20:]
            if not isnan(self._pl[j]):
                lows.insert(0, (j, self._pl[j]))
                del lows[20:]
        return highs, lows

    def _check(
        self,
        i: int,
        pivots: list[tuple[int, float]],
        cond: int,
        positive: bool,
    ) -> int:
        p = self.params
        s = self.rsi
        close = self.close

        def at(series: Sequence[float], back: int) -> float:
            j = i - back
            return series[j] if j >= 0 else NAN

        start = 0 if p.no_confirm else 1
        trigger = (
            at(s, 0) > at(s, 1) or close[i] > at(close, 1)
            if positive
            else (at(s, 0) < at(s, 1) or close[i] < at(close, 1))
        )
        if not (p.no_confirm or trigger):
            return 0
        prsc = self._prsc_low if positive else self._prsc_high
        for x in range(p.max_pivots):
            if x >= len(pivots):
                break
            pos, value = pivots[x]
            length = i - pos + p.pivot_period
            if length > p.max_bars:
                break
            if positive:
                cond_ok = length > 5 and (
                    (cond == 1 and at(s, start) > at(s, length) and at(prsc, start) < nz(value))
                    or (cond == 2 and at(s, start) < at(s, length) and at(prsc, start) > nz(value))
                )
            else:
                cond_ok = length > 5 and (
                    (cond == 1 and at(s, start) < at(s, length) and at(prsc, start) > nz(value))
                    or (cond == 2 and at(s, start) > at(s, length) and at(prsc, start) < nz(value))
                )
            if not cond_ok:
                continue
            slope1 = (at(s, start) - at(s, length)) / (length - start)
            virtual1 = at(s, start) - slope1
            slope2 = (at(close, start) - nz(at(close, length))) / (length - start)
            virtual2 = at(close, start) - slope2
            arrived = True
            for y in range(1 + start, length):
                bad = (
                    (at(s, y) < virtual1 or nz(at(close, y)) < virtual2)
                    if positive
                    else (at(s, y) > virtual1 or nz(at(close, y)) > virtual2)
                )
                if bad:
                    arrived = False
                    break
                virtual1 -= slope1
                virtual2 -= slope2
            if arrived:
                return length
        return 0

    def detect(self, i: int) -> DivResult:
        """Divergence distances (bars back to the earlier pivot, 0 = none) at bar `i`."""
        highs, lows = self._pivots_upto(i)
        return DivResult(
            pos_reg=self._check(i, lows, 1, True),
            neg_reg=self._check(i, highs, 1, False),
            pos_hid=self._check(i, lows, 2, True),
            neg_hid=self._check(i, highs, 2, False),
        )


def single_pivot_divergence(
    rsi: Sequence[float],
    high: Sequence[float],
    low: Sequence[float],
    length: int = 3,
    sticky: int = 20,
) -> tuple[list[bool], list[bool]]:
    """Confluence factor 5: (recent bullish divergence, recent bearish divergence) per bar.

    Compares the latest RSI pivot with the single previous one. Bullish: lower price low but
    higher RSI low, RSI low below 50. Bearish: higher price high but lower RSI high, RSI high
    above 50. The flag stays on for `sticky` bars after the last detection.
    """
    n = len(rsi)
    piv_h = pivot_high(rsi, length, length)
    piv_l = pivot_low(rsi, length, length)
    prh = pph = crh = cph = NAN
    prl = ppl = crl = cpl = NAN
    rec_bull = rec_bear = False
    bd_bar = br_bar = 0
    bull: list[bool] = []
    bear: list[bool] = []
    for i in range(n):
        if not isnan(piv_h[i]):
            prh, pph = crh, cph
            crh, cph = rsi[i - length], high[i - length]
        if not isnan(piv_l[i]):
            prl, ppl = crl, cpl
            crl, cpl = rsi[i - length], low[i - length]
        bull_div = not isnan(prl) and not isnan(crl) and cpl < ppl and crl > prl and crl < 50
        bear_div = not isnan(prh) and not isnan(crh) and cph > pph and crh < prh and crh > 50
        if bull_div:
            rec_bull, bd_bar = True, i
        if bear_div:
            rec_bear, br_bar = True, i
        if i - bd_bar > sticky:
            rec_bull = False
        if i - br_bar > sticky:
            rec_bear = False
        bull.append(rec_bull)
        bear.append(rec_bear)
    return bull, bear
