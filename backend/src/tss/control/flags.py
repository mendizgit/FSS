"""Persistent dashboard switches (control_flags). Pure resolution rules."""

from __future__ import annotations

NEWS = "news"
TELEGRAM = "telegram"
KEYS = (NEWS, TELEGRAM)


def news_on(flags: dict[str, bool]) -> bool:
    """No row = collecting."""
    return flags.get(NEWS, True)


def telegram_on(flags: dict[str, bool], configured: bool, env_paused: bool) -> bool:
    """Credentials are required. A dashboard choice overrides TELEGRAM_ALERTS from .env; with no
    choice stored, the .env value decides."""
    if not configured:
        return False
    return flags.get(TELEGRAM, not env_paused)
