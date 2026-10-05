"""Hand-computed checks for tss.domain.calculations (Arch §5)."""

from datetime import UTC, datetime, timedelta

import pytest

from tss.domain.calculations import (
    BAR,
    Direction,
    direction,
    has_gap,
    is_closed,
    nearest_within,
    pct_change,
    rvol,
    window_price_change,
    window_sum_change,
)

T0 = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)


def test_pct_change_basic_and_guards() -> None:
    assert pct_change(110.0, 100.0) == pytest.approx(10.0)
    assert pct_change(90.0, 100.0) == pytest.approx(-10.0)
    assert pct_change(100.0, 0.0) is None
    assert pct_change(100.0, -1.0) is None
    assert pct_change(None, 100.0) is None
    assert pct_change(100.0, None) is None


def test_direction_deadband() -> None:
    assert direction(0.3, 0.2) == Direction.RISING
    assert direction(-0.3, 0.2) == Direction.FALLING
    assert direction(0.2, 0.2) == Direction.FLAT  # boundary is flat (strict inequality)
    assert direction(0.0, 0.0) == Direction.FLAT
    assert direction(0.0001, 0.0) == Direction.RISING
    assert direction(None, 0.2) is None


def test_is_closed_boundary() -> None:
    assert is_closed(T0, T0 + BAR)  # open_time + 15m <= now
    assert not is_closed(T0, T0 + BAR - timedelta(seconds=1))


def test_rvol_median_of_prior_bars() -> None:
    prior = [10.0, 20.0, 30.0, 40.0]  # median 25
    assert rvol([*prior, 50.0], lookback=4) == pytest.approx(2.0)
    # only the last lookback+1 bars count
    assert rvol([999.0, *prior, 50.0], lookback=4) == pytest.approx(2.0)


def test_rvol_none_cases() -> None:
    assert rvol([1.0, 2.0, 3.0], lookback=3) is None  # fewer than lookback + 1 bars
    assert rvol([0.0, 0.0, 0.0, 5.0], lookback=3) is None  # zero median
    assert rvol([1.0, None, 3.0, 5.0], lookback=3) is None  # missing value is not dropped


def test_window_sum_change() -> None:
    # n=2: previous sum 1+2=3, last sum 3+6=9 -> +200 %
    assert window_sum_change([1.0, 2.0, 3.0, 6.0], 2) == pytest.approx(200.0)
    assert window_sum_change([1.0, 2.0, 3.0], 2) is None
    assert window_sum_change([1.0, None, 3.0, 6.0], 2) is None
    assert window_sum_change([0.0, 0.0, 3.0, 6.0], 2) is None  # previous sum 0


def test_window_price_change() -> None:
    # n=4: close[last]=105 vs close[last-4]=100
    assert window_price_change([100.0, 101.0, 102.0, 103.0, 105.0], 4) == pytest.approx(5.0)
    assert window_price_change([100.0, 105.0], 4) is None


def test_has_gap() -> None:
    times = [T0 + i * BAR for i in range(6)]
    assert not has_gap(times, 4)
    assert has_gap(times, 7)  # too few bars
    holey = [*times[:3], times[4], times[5]]  # missing index 3
    assert has_gap(holey, 4)
    assert not has_gap(holey, 2)  # gap is outside the newest 2 bars


def test_nearest_within_never_interpolates() -> None:
    items = [(T0, 1.0), (T0 + timedelta(seconds=300), 2.0)]
    assert nearest_within(items, T0 + timedelta(seconds=80), 90) == 1.0
    assert nearest_within(items, T0 + timedelta(seconds=220), 90) == 2.0
    assert nearest_within(items, T0 + timedelta(seconds=150), 90) is None
