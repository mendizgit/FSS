"""Paper-trade maths (pure): entry levels, bar scan for stop / target, settlement.

Dummy money only: nothing here talks to an exchange. Prices come from closed 5m bars. When a
single bar touches both the stop and the target the stop wins (the pessimistic reading).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import NamedTuple

LONG_FLIPS = ("BUY", "BULL_T")
SHORT_FLIPS = ("SELL", "BEAR_T")
FLIP_WINDOW_BARS = 4  # a side-aligned 15m flip within the last hour confirms the entry


class Bar5(NamedTuple):
    open_time: datetime
    close_time: datetime
    high: float
    low: float
    close: float


@dataclass(frozen=True)
class Levels:
    entry: float
    stop: float
    target: float
    notional: float
    qty: float


@dataclass(frozen=True)
class Exit:
    reason: str  # target | stop | invalidated | left_pool | timeout
    price: float
    time: datetime
    mfe_pct: float
    mae_pct: float


@dataclass(frozen=True)
class Settlement:
    fees: float
    pnl: float
    r_multiple: float


def levels(
    side: str,
    close: float,
    margin: float,
    leverage: float,
    stop_pct: float,
    reward_risk: float,
    slippage_pct: float,
) -> Levels:
    """Entry at the 5m close with adverse slippage, stop `stop_pct` away, target `reward_risk` x."""
    slip = slippage_pct / 100
    sign = 1 if side == "long" else -1
    entry = close * (1 + sign * slip)
    stop = entry * (1 - sign * stop_pct / 100)
    target = entry * (1 + sign * stop_pct * reward_risk / 100)
    notional = margin * leverage
    return Levels(entry, stop, target, notional, notional / entry)


def excursions(side: str, entry: float, bars: list[Bar5]) -> tuple[float, float]:
    """(best, worst) move for the side in percent of entry over the bars (worst <= 0 <= best)."""
    if not bars:
        return 0.0, 0.0
    hi = max(b.high for b in bars)
    lo = min(b.low for b in bars)
    if side == "long":
        return max(0.0, (hi / entry - 1) * 100), min(0.0, (lo / entry - 1) * 100)
    return max(0.0, (1 - lo / entry) * 100), min(0.0, (1 - hi / entry) * 100)


def scan(side: str, lv: Levels, bars: list[Bar5], slippage_pct: float) -> Exit | None:
    """First bar (oldest first) that touches the stop or the target, or None."""
    slip = slippage_pct / 100
    for i, b in enumerate(bars):
        if side == "long":
            stop_hit, tp_hit = b.low <= lv.stop, b.high >= lv.target
        else:
            stop_hit, tp_hit = b.high >= lv.stop, b.low <= lv.target
        if not (stop_hit or tp_hit):
            continue
        mfe, mae = excursions(side, lv.entry, bars[: i + 1])
        if stop_hit:  # market-like fill, slips against the trade
            px = lv.stop * (1 - slip) if side == "long" else lv.stop * (1 + slip)
            return Exit("stop", px, b.close_time, mfe, mae)
        return Exit("target", lv.target, b.close_time, mfe, mae)  # resting limit: no slippage
    return None


def market_exit(side: str, reason: str, bars: list[Bar5], lv: Levels, slippage_pct: float) -> Exit:
    """Close at the newest closed bar's close, slipping against the trade."""
    last = bars[-1]
    slip = slippage_pct / 100
    px = last.close * (1 - slip) if side == "long" else last.close * (1 + slip)
    mfe, mae = excursions(side, lv.entry, bars)
    return Exit(reason, px, last.close_time, mfe, mae)


def settle(side: str, lv: Levels, exit_price: float, stop_pct: float, fee_pct: float) -> Settlement:
    gross = (exit_price - lv.entry) * lv.qty * (1 if side == "long" else -1)
    fees = (lv.entry + exit_price) * lv.qty * fee_pct / 100
    pnl = gross - fees
    risk = lv.notional * stop_pct / 100
    return Settlement(fees, pnl, pnl / risk)


def open_at(opened_at: datetime, closed_at: datetime | None, at: datetime) -> bool:
    """True when a trade was open at `at` (an alert raised then must not open another)."""
    return opened_at <= at and (closed_at is None or closed_at > at)


def flip_tags(side: str, events: list[tuple[str, int]]) -> tuple[str | None, bool]:
    """('BUY:2,BULL_T:2' | None, confirmed) from (event, bars_ago) pairs of the 15m row."""
    own = LONG_FLIPS if side == "long" else SHORT_FLIPS
    mine = [(e, ago) for e, ago in events if e in own]
    text = ",".join(f"{e}:{ago}" for e, ago in mine) or None
    return text, any(ago <= FLIP_WINDOW_BARS for _, ago in mine)
