"""Telegram alert text and send policy (F10). Pure functions.

One message per new 15m entry (HTML parse mode; every inserted value is escaped):

    <b>UMAUSDT.P</b>
    Entry : 🟢 Long                (🔴 Short)
    Time : 15 min
    Score : 4/5 (ST, 1H, EMA, DIV)
    Bar close : 14:45 IST          (close time of the 15m bar the entry is based on)
    4H trend : ✓ With              (✗ Against; — when unknown). Informational: never a filter.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from html import escape

from tss.core.time import to_ist

TIME_LABEL = {"5m": "5 min", "15m": "15 min", "1h": "1 hour"}
BIAS_LABEL = {"long": "🟢 Long", "short": "🔴 Short"}
SCORE_OF = 5

# A late alert is worse than none: an entry detected longer ago than this is never sent.
SETUP_MAX_AGE = timedelta(minutes=10)


def display_symbol(symbol: str) -> str:
    """BTC_USDT -> BTCUSDT.P (perpetual notation)."""
    return f"{symbol.replace('_', '')}.P"


def format_setup_message(
    *,
    symbol: str,
    bias: str,
    trigger_timeframe: str,
    score: int | None,
    factors: str | None,
    trigger_bar_close_time: datetime,
    against_htf: bool | None,
) -> str:
    htf = "—" if against_htf is None else ("✗ Against" if against_htf else "✓ With")
    detail = f" ({escape(factors.replace(',', ', '))})" if factors else ""
    lines = [
        f"<b>{escape(display_symbol(symbol))}</b>",
        f"Entry : {BIAS_LABEL.get(bias, escape(bias))}",
        f"Time : {escape(TIME_LABEL.get(trigger_timeframe, trigger_timeframe))}",
        f"Score : {'—' if score is None else score}/{SCORE_OF}{detail}",
        f"Bar close : {to_ist(trigger_bar_close_time).strftime('%H:%M')} IST",
        f"4H trend : {htf}",
    ]
    return "\n".join(lines)


def connectivity_message() -> str:
    return "TSS test message: Telegram alerts are connected."
