"""Telegram alert text and send policy (F10). Pure functions.

One message per new Long / Short setup (HTML parse mode; every inserted value is escaped):

    <b>UMAUSDT.P</b>
    Setup : 🟢 Long                (🔴 Short)
    Trigger : 5 min BullT          (the 5m / 15m event that qualified the setup)
    1h confirm : BullT, 3 bars ago
    Bar close : 14:35 IST          (close time of the trigger bar)
    4H trend : ✓ With              (✗ Against; — when unknown). Informational: never a filter.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from html import escape

from tss.core.time import to_ist

NOTIFY_TIMEFRAMES = ("5m", "15m")  # setups are triggered on these; 1h is the confirmation

TIME_LABEL = {"5m": "5 min", "15m": "15 min", "1h": "1 hour"}
EVENT_LABEL = {"BUY": "Buy", "SELL": "Sell", "BULL_T": "BullT", "BEAR_T": "BearT"}
BIAS_LABEL = {"long": "🟢 Long", "short": "🔴 Short"}

# A late alert is worse than none: a setup detected longer ago than this is never sent.
SETUP_MAX_AGE = timedelta(minutes=10)


def display_symbol(symbol: str) -> str:
    """BTC_USDT -> BTCUSDT.P (perpetual notation)."""
    return f"{symbol.replace('_', '')}.P"


def _ago(bars: int) -> str:
    return "now" if bars == 0 else f"{bars} bar{'s' if bars != 1 else ''} ago"


def format_setup_message(
    *,
    symbol: str,
    bias: str,
    trigger_timeframe: str,
    trigger_event: str,
    htf_event: str,
    htf_bars_ago: int,
    trigger_bar_close_time: datetime,
    against_htf: bool | None,
) -> str:
    htf = "—" if against_htf is None else ("✗ Against" if against_htf else "✓ With")
    lines = [
        f"<b>{escape(display_symbol(symbol))}</b>",
        f"Setup : {BIAS_LABEL.get(bias, escape(bias))}",
        f"Trigger : {escape(TIME_LABEL.get(trigger_timeframe, trigger_timeframe))} "
        f"{escape(EVENT_LABEL.get(trigger_event, trigger_event))}",
        f"1h confirm : {escape(EVENT_LABEL.get(htf_event, htf_event))}, {_ago(htf_bars_ago)}",
        f"Bar close : {to_ist(trigger_bar_close_time).strftime('%H:%M')} IST",
        f"4H trend : {htf}",
    ]
    return "\n".join(lines)


def connectivity_message() -> str:
    return "TSS test message: Telegram alerts are connected."
