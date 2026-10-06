"""Next scheduled run times (Arch §8), derived from the cron rules. Pure functions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from tss.core.time import next_boundary, to_ist, utc_day_start


def in_quiet_hours(now: datetime, pause_hour: int, resume_hour: int) -> bool:
    """True while the IST wall clock is in [pause_hour:00, resume_hour:00) (wraps midnight)."""
    hour = to_ist(now).hour
    if pause_hour == resume_hour:
        return False
    if pause_hour < resume_hour:
        return pause_hour <= hour < resume_hour
    return hour >= pause_hour or hour < resume_hour


@dataclass(frozen=True)
class PauseState:
    paused: bool
    reason: str | None  # why the system is paused / why it is running despite the daily pause
    until: datetime | None  # when a manual choice stops applying
    manual: bool


def next_ist_hour(after: datetime, hour: int) -> datetime:
    """First HH:00 IST strictly after `after`, as UTC."""
    ist = to_ist(after)
    cand = ist.replace(hour=hour, minute=0, second=0, microsecond=0)
    if cand <= ist:
        cand += timedelta(days=1)
    return cand.astimezone(UTC)


def pause_state(
    now: datetime,
    override_enabled: bool | None,
    override_at: datetime | None,
    pause_hour: int,
    resume_hour: int,
) -> PauseState:
    """Daily pause [pause_hour, resume_hour) IST plus the dashboard's Pause / Start override.

    Pause (override False) holds until the next resume hour. Start (override True) holds until
    the next pause hour, so a start inside the daily pause keeps running until that pause begins
    again. Afterwards the daily schedule applies.
    """
    daily = in_quiet_hours(now, pause_hour, resume_hour)
    if override_enabled is not None and override_at is not None:
        if override_enabled is False:
            until = next_ist_hour(override_at, resume_hour)
            if now < until:
                return PauseState(True, f"manual pause until {resume_hour:02d}:00 IST", until, True)
        else:
            until = next_ist_hour(override_at, pause_hour)
            if now < until:
                return PauseState(False, f"manual start until {pause_hour:02d}:00 IST", until, True)
    reason = f"daily pause {pause_hour:02d}:00-{resume_hour:02d}:00 IST" if daily else None
    return PauseState(daily, reason, None, False)


def next_snapshot(now: datetime) -> datetime:
    return next_boundary(now, 5)


def next_pipeline(now: datetime) -> datetime:
    """15-minute boundary + 20 s; if this boundary's run is still ahead, it is the next one."""
    run = next_boundary(now - timedelta(seconds=20), 15) + timedelta(seconds=20)
    return run


def next_signal(now: datetime) -> datetime:
    """5-minute boundary + 5 s. On 15-minute boundaries the pipeline (+20 s) also triggers a
    signal run when it finishes, with the new selection."""
    return next_boundary(now - timedelta(seconds=5), 5) + timedelta(seconds=5)


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
