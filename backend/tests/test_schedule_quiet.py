from datetime import UTC, datetime, timedelta

from tss.control.schedule import PauseState, in_quiet_hours, pause_state


def utc(h: int, m: int = 0) -> datetime:
    return datetime(2026, 10, 5, h, m, tzinfo=UTC)


def test_quiet_window_is_midnight_to_five_ist() -> None:
    # 00:00 IST = 18:30 UTC, 05:00 IST = 23:30 UTC
    assert not in_quiet_hours(utc(18, 29), 0, 5)
    assert in_quiet_hours(utc(18, 30), 0, 5)
    assert in_quiet_hours(utc(22), 0, 5)
    assert in_quiet_hours(utc(23, 29), 0, 5)
    assert not in_quiet_hours(utc(23, 30), 0, 5)
    assert not in_quiet_hours(utc(12), 0, 5)


def test_window_wrapping_midnight_and_empty_window() -> None:
    assert in_quiet_hours(utc(18, 30), 23, 6)  # 00:00 IST is inside 23 -> 6
    assert not in_quiet_hours(utc(12), 23, 6)  # 17:30 IST
    assert not in_quiet_hours(utc(12), 5, 5)


# --- dashboard Pause / Start override (IST = UTC+5:30; helper ist() builds an IST wall time) ---


def ist(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 10, day, hour, minute, tzinfo=UTC) - timedelta(hours=5, minutes=30)


def ps(now: datetime, enabled: bool | None = None, at: datetime | None = None) -> PauseState:
    return pause_state(now, enabled, at, 0, 5)


def test_no_override_follows_daily_pause() -> None:
    assert ps(ist(7, 3)).paused and not ps(ist(7, 3)).manual
    assert not ps(ist(7, 12)).paused


def test_manual_pause_lasts_until_next_0500() -> None:
    at = ist(7, 14)
    assert ps(ist(7, 20), False, at).paused
    assert ps(ist(8, 4, 59), False, at).paused
    assert ps(ist(8, 4, 59), False, at).until == ist(8, 5)
    assert not ps(ist(8, 5), False, at).paused  # back to the daily schedule: running


def test_pause_inside_daily_window_resumes_at_0500() -> None:
    at = ist(7, 2)
    assert ps(ist(7, 4, 59), False, at).paused
    assert not ps(ist(7, 5), False, at).paused


def test_start_inside_daily_pause_runs_until_next_midnight() -> None:
    at = ist(7, 1)
    st = ps(ist(7, 20), True, at)
    assert not st.paused and st.manual and st.until == ist(8, 0)
    assert not ps(ist(7, 23, 59), True, at).paused
    assert ps(ist(8, 0), True, at).paused  # daily pause is back


def test_start_outside_daily_window_changes_nothing() -> None:
    at = ist(7, 15)  # e.g. after a manual pause at 14:00
    assert not ps(ist(7, 18), True, at).paused
    assert ps(ist(8, 0, 1), True, at).paused  # auto pause at 00:00


def test_new_choice_replaces_old() -> None:
    # paused at 14:00, started at 15:00 (override now = start), runs; at 00:00 it auto-pauses
    assert not ps(ist(7, 16), True, ist(7, 15)).paused
