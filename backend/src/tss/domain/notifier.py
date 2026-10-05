"""Telegram alert text and send policy (F10). Pure functions.

Alert format (HTML parse mode; every inserted value is escaped):

    <b>UMAUSDT.P</b>
    Time : 5 min
    Signal : 🟢 Buy          (🔴 Sell; "—" for a trend flip without a BUY/SELL signal)
    Trend : BullT            (BearT)
    <i>Not financial advice</i>
"""

from __future__ import annotations

from datetime import timedelta
from html import escape

NOTIFY_EVENTS = ("BUY", "SELL", "BULL_T", "BEAR_T")  # TD events are not pushed
DISCLAIMER = "Not financial advice"

TIME_LABEL = {"5m": "5 min", "15m": "15 min", "1h": "1 hour"}
SIGNAL_LABEL = {"BUY": "🟢 Buy", "SELL": "🔴 Sell"}  # BULL_T / BEAR_T alone carry no signal
TREND_LABEL = {"BUY": "BullT", "BULL_T": "BullT", "SELL": "BearT", "BEAR_T": "BearT"}

# A late alert is worse than none: events older than this (by timeframe) are never sent.
MAX_AGE = {"5m": timedelta(minutes=15), "15m": timedelta(minutes=30), "1h": timedelta(hours=2)}
DEFAULT_MAX_AGE = timedelta(minutes=15)


def display_symbol(symbol: str) -> str:
    """BTC_USDT -> BTCUSDT.P (perpetual notation)."""
    return f"{symbol.replace('_', '')}.P"


def format_event_message(
    *, symbol: str, timeframe: str, event: str, against_htf: bool | None
) -> str:
    footer = DISCLAIMER if not against_htf else f"✗ Against the 4H trend · {DISCLAIMER}"
    lines = [
        f"<b>{escape(display_symbol(symbol))}</b>",
        f"Time : {escape(TIME_LABEL.get(timeframe, timeframe))}",
        f"Signal : {SIGNAL_LABEL.get(event, '—')}",
        f"Trend : {escape(TREND_LABEL.get(event, event))}",
        f"<i>{escape(footer)}</i>",
    ]
    return "\n".join(lines)


def connectivity_message() -> str:
    return f"TSS test message: Telegram alerts are connected.\n{DISCLAIMER}."
