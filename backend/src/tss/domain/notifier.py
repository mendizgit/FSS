"""Telegram alert text and send policy (F10). Pure functions; plain text only."""

from __future__ import annotations

from datetime import datetime, timedelta

from tss.core.time import format_ist

NOTIFY_EVENTS = ("BUY", "SELL", "BULL_T", "BEAR_T")  # TD events are not pushed
DISCLAIMER = "Market analysis only. Not financial advice."
EVENT_TEXT = {"BUY": "BUY", "SELL": "SELL", "BULL_T": "bullT", "BEAR_T": "bearT"}
ICON = {"BUY": "▲", "BULL_T": "▲", "SELL": "▼", "BEAR_T": "▼"}

# A late alert is worse than none: events older than this (by timeframe) are never sent.
MAX_AGE = {"5m": timedelta(minutes=15), "15m": timedelta(minutes=30), "1h": timedelta(hours=2)}
DEFAULT_MAX_AGE = timedelta(minutes=15)


def format_price(value: float | None) -> str:
    if value is None:
        return "unavailable"
    abs_v = abs(value)
    digits = (
        2 if abs_v >= 1000 else 3 if abs_v >= 10 else 4 if abs_v >= 1 else 5 if abs_v >= 0.01 else 7
    )
    return f"{value:,.{digits}f}"


def format_event_message(
    *,
    symbol: str,
    timeframe: str,
    event: str,
    against_htf: bool | None,
    price: float | None,
    price_time: datetime | None,
    bar_close_time: datetime,
) -> str:
    label = EVENT_TEXT.get(event, event)
    lines = [
        f"{ICON.get(event, '•')} {label} · {symbol} · {timeframe}",
        f"Bar closed: {format_ist(bar_close_time)}",
        f"Last price: {format_price(price)}"
        + (f" (snapshot {format_ist(price_time)})" if price is not None and price_time else ""),
    ]
    if against_htf:
        lines.append("✗ Against the 4H trend")
    elif against_htf is False:
        lines.append("✓ With the 4H trend")
    lines.append(DISCLAIMER)
    return "\n".join(lines)


def connectivity_message() -> str:
    return f"TSS test message: Telegram alerts are connected.\n{DISCLAIMER}"
