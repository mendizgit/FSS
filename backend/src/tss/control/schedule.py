"""Next scheduled run times (Arch §8), derived from the cron rules. Pure functions."""

from __future__ import annotations

from datetime import datetime, timedelta

from tss.core.time import next_boundary, utc_day_start


def next_snapshot(now: datetime) -> datetime:
    return next_boundary(now, 5)


def next_pipeline(now: datetime) -> datetime:
    """15-minute boundary + 20 s; if this boundary's run is still ahead, it is the next one."""
    run = next_boundary(now - timedelta(seconds=20), 15) + timedelta(seconds=20)
    return run


def next_retention(now: datetime) -> datetime:
    today = utc_day_start(now) + timedelta(minutes=30)
    return today if today > now else today + timedelta(days=1)


def next_universe(last_run: datetime | None, refresh_hours: int, now: datetime) -> datetime | None:
    if last_run is None:
        return None
    nxt = last_run + timedelta(hours=refresh_hours)
    return nxt if nxt > now else now
