from datetime import UTC, datetime

from tss.control.schedule import in_quiet_hours


def utc(h: int, m: int = 0) -> datetime:
    return datetime(2026, 10, 5, h, m, tzinfo=UTC)


def test_quiet_window_is_midnight_to_six_ist() -> None:
    # 00:00 IST = 18:30 UTC, 06:00 IST = 00:30 UTC
    assert not in_quiet_hours(utc(18, 29), 0, 6)
    assert in_quiet_hours(utc(18, 30), 0, 6)
    assert in_quiet_hours(utc(22), 0, 6)
    assert in_quiet_hours(utc(0, 29), 0, 6)
    assert not in_quiet_hours(utc(0, 30), 0, 6)
    assert not in_quiet_hours(utc(12), 0, 6)


def test_window_wrapping_midnight_and_empty_window() -> None:
    assert in_quiet_hours(utc(18, 30), 23, 6)  # 00:00 IST is inside 23 -> 6
    assert not in_quiet_hours(utc(12), 23, 6)  # 17:30 IST
    assert not in_quiet_hours(utc(12), 5, 5)
