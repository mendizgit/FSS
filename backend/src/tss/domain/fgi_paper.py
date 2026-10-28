"""FGI strategy paper-trade maths (pure): entry plan, 5m bar scan with partial exits.

Dummy money only. Exits follow the strategy: ATR / swing stop (capped), TP1 closes a fraction at
`tp1_atr` x ATR, then the stop moves to break-even once a closed 15m bar has reached TP1, the rest
exits at TP2 `tp2_atr` x ATR, or at the next 5m open after a closed 15m bar shows the higher-
timeframe trend against the trade. A bar that touches the stop and a target: the stop wins.
Stops and flip exits fill with slippage against the trade; targets are resting limits.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import NamedTuple

BE_ATR = 0.1  # break-even stop sits this many ATR beyond the entry


class Bar5(NamedTuple):
    open_time: datetime
    close_time: datetime
    open: float
    high: float
    low: float
    close: float


class Boundary(NamedTuple):
    """The 15m bar that closed at a 5m bar's close: high / low, ATR and the trend flags."""

    high: float
    low: float
    atr: float
    trend_bull: bool
    trend_bear: bool


@dataclass(frozen=True)
class Plan:
    entry: float
    stop: float
    tp1: float
    tp2: float
    notional: float
    qty: float


@dataclass
class State:
    side: str
    entry: float
    stop: float
    stop0: float
    tp1: float
    tp2: float
    qty: float
    remaining: float = 1.0
    tp1_done: bool = False
    be: bool = False
    flip_pending: bool = False
    gross: float = 0.0
    fees: float = 0.0


@dataclass(frozen=True)
class Exit:
    reason: str  # stop | be | tp2 | flip
    price: float
    time: datetime


@dataclass(frozen=True)
class Settlement:
    fees: float
    pnl: float
    r_multiple: float


def plan(
    side: str,
    signal_close: float,
    atr: float,
    raw_stop: float,
    fill_close: float,
    *,
    margin: float,
    leverage: float,
    stop_cap_pct: float,
    tp1_atr: float,
    tp2_atr: float,
    slippage_pct: float,
) -> Plan | None:
    """Entry at the newest 5m close with adverse slippage; stop never wider than the cap from the
    fill; targets from the signal bar's close. None when the levels are not on the right side."""
    long = side == "long"
    sign = 1 if long else -1
    entry = fill_close * (1 + sign * slippage_pct / 100)
    cap = entry * (1 - sign * stop_cap_pct / 100)
    stop = max(raw_stop, cap) if long else min(raw_stop, cap)
    tp1 = signal_close + sign * tp1_atr * atr
    tp2 = signal_close + sign * tp2_atr * atr
    if (entry - stop) * sign <= 0 or (tp1 - entry) * sign <= 0 or (tp2 - tp1) * sign <= 0:
        return None
    notional = margin * leverage
    return Plan(entry, stop, tp1, tp2, notional, notional / entry)


def _leg(st: State, fraction: float, price: float, fee_pct: float) -> None:
    sign = 1 if st.side == "long" else -1
    st.gross += (price - st.entry) * st.qty * fraction * sign
    st.fees += (st.entry + price) * st.qty * fraction * fee_pct / 100
    st.remaining -= fraction


def advance(
    st: State,
    bars: list[Bar5],
    boundaries: dict[datetime, Boundary],
    *,
    tp1_fraction: float,
    slippage_pct: float,
    fee_pct: float,
) -> Exit | None:
    """Apply closed 5m bars (oldest first) to the open trade; an Exit when it is fully closed."""
    long = st.side == "long"
    slip = slippage_pct / 100
    against = (1 - slip) if long else (1 + slip)
    for b in bars:
        if st.flip_pending:  # the 15m bar before showed the trend against us: out at this open
            px = b.open * against
            _leg(st, st.remaining, px, fee_pct)
            return Exit("flip", px, b.open_time)
        stop_hit = b.low <= st.stop if long else b.high >= st.stop
        if stop_hit:
            px = st.stop * against
            _leg(st, st.remaining, px, fee_pct)
            return Exit("be" if st.be else "stop", px, b.close_time)
        if not st.tp1_done and (b.high >= st.tp1 if long else b.low <= st.tp1):
            _leg(st, tp1_fraction, st.tp1, fee_pct)
            st.tp1_done = True
        if st.tp1_done and (b.high >= st.tp2 if long else b.low <= st.tp2):
            _leg(st, st.remaining, st.tp2, fee_pct)
            return Exit("tp2", st.tp2, b.close_time)
        edge = boundaries.get(b.close_time)
        if edge is not None:
            if not st.be and (edge.high >= st.tp1 if long else edge.low <= st.tp1):
                st.stop = st.entry + (BE_ATR if long else -BE_ATR) * edge.atr
                st.be = True
            if (long and edge.trend_bear) or (not long and edge.trend_bull):
                st.flip_pending = True
    return None


def settle(st: State) -> Settlement:
    """Net result of a fully closed trade; R is against the initial stop distance."""
    pnl = st.gross - st.fees
    risk = st.qty * abs(st.entry - st.stop0)
    return Settlement(st.fees, pnl, pnl / risk if risk > 0 else 0.0)


def excursions(side: str, entry: float, bars: list[Bar5]) -> tuple[float, float]:
    """(best, worst) move for the side in percent of entry over the bars (worst <= 0 <= best)."""
    if not bars:
        return 0.0, 0.0
    hi = max(b.high for b in bars)
    lo = min(b.low for b in bars)
    if side == "long":
        return max(0.0, (hi / entry - 1) * 100), min(0.0, (lo / entry - 1) * 100)
    return max(0.0, (1 - lo / entry) * 100), min(0.0, (1 - hi / entry) * 100)
