"""Telegram alert text and send policy (F10). Pure functions.

Alert format (HTML parse mode; every inserted value is escaped):

    <b>UMAUSDT.P</b>
    Time : 5 min
    Bar close : 14:35 IST    (close time of the signal bar)
    Signal : 🟢 Buy          (🔴 Sell; "—" for a trend flip or TD without a BUY/SELL signal)
    Trend : BullT            (BearT; "TD Bull" / "TD Bear" for TD events)
    <i>✗ Against the 4H trend</i>   (only when the event goes against the 4H trend)
"""

from __future__ import annotations

from datetime import datetime, timedelta
from html import escape

from tss.core.time import to_ist

NOTIFY_EVENTS = ("BUY", "SELL", "BULL_T", "BEAR_T", "TD_BULL", "TD_BEAR")
NOTIFY_TIMEFRAMES = ("5m", "15m")  # 1h events are shown on the dashboard only

TIME_LABEL = {"5m": "5 min", "15m": "15 min", "1h": "1 hour"}
SIGNAL_LABEL = {"BUY": "🟢 Buy", "SELL": "🔴 Sell"}  # BULL_T / BEAR_T alone carry no signal
TREND_LABEL = {
    "BUY": "BullT",
    "BULL_T": "BullT",
    "SELL": "BearT",
    "BEAR_T": "BearT",
    "TD_BULL": "TD Bull",
    "TD_BEAR": "TD Bear",
}

# A late alert is worse than none: events older than this (by timeframe) are never sent.
MAX_AGE = {"5m": timedelta(minutes=15), "15m": timedelta(minutes=30), "1h": timedelta(hours=2)}
DEFAULT_MAX_AGE = timedelta(minutes=15)


def display_symbol(symbol: str) -> str:
    """BTC_USDT -> BTCUSDT.P (perpetual notation)."""
    return f"{symbol.replace('_', '')}.P"


def format_event_message(
    *, symbol: str, timeframe: str, event: str, against_htf: bool | None, bar_close_time: datetime
) -> str:
    lines = [
        f"<b>{escape(display_symbol(symbol))}</b>",
        f"Time : {escape(TIME_LABEL.get(timeframe, timeframe))}",
        f"Bar close : {to_ist(bar_close_time).strftime('%H:%M')} IST",
        f"Signal : {SIGNAL_LABEL.get(event, '—')}",
        f"Trend : {escape(TREND_LABEL.get(event, event))}",
    ]
    if against_htf:
        lines.append("<i>✗ Against the 4H trend</i>")
    return "\n".join(lines)


def connectivity_message() -> str:
    return "TSS test message: Telegram alerts are connected."
