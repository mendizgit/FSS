"""Next scheduled run times (Arch §8), derived from the cron rules. Pure functions."""

from __future__ import annotations

from datetime import datetime, timedelta

from tss.core.time import next_boundary, to_ist, utc_day_start


def in_quiet_hours(now: datetime, pause_hour: int, resume_hour: int) -> bool:
    """True while the IST wall clock is in [pause_hour:00, resume_hour:00) (wraps midnight)."""
    hour = to_ist(now).hour
    if pause_hour == resume_hour:
        return False
    if pause_hour < resume_hour:
        return pause_hour <= hour < resume_hour
    return hour >= pause_hour or hour < resume_hour


def next_snapshot(now: datetime) -> datetime:
    return next_boundary(now, 5)


def next_pipeline(now: datetime) -> datetime:
    """15-minute boundary + 20 s; if this boundary's run is still ahead, it is the next one."""
    run = next_boundary(now - timedelta(seconds=20), 15) + timedelta(seconds=20)
    return run


def next_signal(now: datetime) -> datetime:
    """5-minute boundary + 20 s. On 15-minute boundaries the pipeline (same +20 s) triggers the
    signal run when it finishes, so that is the earliest start there too."""
    return next_boundary(now - timedelta(seconds=20), 5) + timedelta(seconds=20)


def next_news(now: datetime) -> datetime:
    """15-minute boundary + 50 s (same rule as the pipeline, different offset)."""
    return next_boundary(now - timedelta(seconds=50), 15) + timedelta(seconds=50)


def next_retention(now: datetime) -> datetime:
    today = utc_day_start(now) + timedelta(minutes=30)
    return today if today > now else today + timedelta(days=1)


def next_universe(last_run: datetime | None, refresh_hours: int, now: datetime) -> datetime | None:
    if last_run is None:
        return None
    nxt = last_run + timedelta(hours=refresh_hours)
    return nxt if nxt > now else now
