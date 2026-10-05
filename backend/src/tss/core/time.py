"""Time helpers. Store UTC, display IST. Domain code receives time; it never reads the clock."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from tss.core.errors import ValidationError

IST = ZoneInfo("Asia/Kolkata")


def utc_now() -> datetime:
    return datetime.now(UTC)


def ensure_utc(dt: datetime) -> datetime:
    """Return an aware UTC datetime; naive input is rejected, not guessed."""
    if dt.tzinfo is None:
        raise ValidationError(
            "time",
            "P0",
            "ensure_utc",
            "naive datetime not allowed; timestamps must be timezone-aware",
        )
    return dt.astimezone(UTC)


def floor_to_minutes(dt: datetime, minutes: int) -> datetime:
    """Floor to a cron-style boundary (e.g. 15 -> :00/:15/:30/:45) in UTC."""
    dt = ensure_utc(dt)
    floored = dt.replace(second=0, microsecond=0)
    return floored - timedelta(minutes=floored.minute % minutes)


def next_boundary(dt: datetime, minutes: int) -> datetime:
    """Next cron boundary strictly after dt."""
    return floor_to_minutes(dt, minutes) + timedelta(minutes=minutes)


def utc_day_start(dt: datetime) -> datetime:
    return ensure_utc(dt).replace(hour=0, minute=0, second=0, microsecond=0)


def utc_date(dt: datetime) -> date:
    return ensure_utc(dt).date()


def to_ist(dt: datetime) -> datetime:
    return ensure_utc(dt).astimezone(IST)


def format_ist(dt: datetime) -> str:
    """Display format, e.g. '2026-10-05 16:45:00 IST'."""
    return to_ist(dt).strftime("%Y-%m-%d %H:%M:%S IST")
