"""Hand-computed checks for the Pine primitives (skills/pine-port.md semantics)."""

import math
from datetime import UTC, datetime, timedelta

import pytest

from tss.indicators.primitives import (
    atr,
    bollinger,
    change,
    ema,
    highest,
    isnan,
    lowest,
    pivot_high,
    pivot_low,
    rma,
    rsi,
    sma,
    stdev,
    true_range,
    vwap_daily,
)

NAN = math.nan


def same(actual: list[float], expected: list[float], tol: float = 1e-9) -> None:
    assert len(actual) == len(expected)
    for a, e in zip(actual, expected, strict=True):
        if math.isnan(e):
            assert isnan(a), (actual, expected)
        else:
            assert a == pytest.approx(e, abs=tol), (actual, expected)


def test_sma() -> None:
    same(sma([1, 2, 3, 4, 5], 3), [NAN, NAN, 2, 3, 4])
    same(sma([1, NAN, 3, 4, 5], 3), [NAN, NAN, NAN, NAN, 4])  # NaN inside the window


def test_ema_seeded_with_sma() -> None:
    # alpha = 2/(3+1) = 0.5: seed 2 at index 2, then 0.5*4+0.5*2 = 3, 0.5*5+0.5*3 = 4
    same(ema([1, 2, 3, 4, 5], 3), [NAN, NAN, 2, 3, 4])
    # leading NaN (e.g. an absolute change series): the seed waits for a full window
    same(ema([NAN, 1, 2, 3, 6], 3), [NAN, NAN, NAN, 2, 4])


def test_rma_wilder() -> None:
    # alpha = 1/3: seed 2, then 4/3 + 4/3 = 8/3, then 5/3 + 16/9 = 31/9
    same(rma([1, 2, 3, 4, 5], 3), [NAN, NAN, 2, 8 / 3, 31 / 9])


def test_change() -> None:
    same(change([1, 3, 2]), [NAN, 2, -1])


def test_rsi_hand_computed() -> None:
    # closes 10,11,12,11,12,13 length 3: up rma = 2/3, 7/9, 23/27; down rma = 1/3, 2/9, 4/27
    out = rsi([10, 11, 12, 11, 12, 13], 3)
    same(out, [NAN, NAN, NAN, 100 - 100 / 3, 100 - 100 / 4.5, 100 - 100 / 6.75], tol=1e-9)


def test_rsi_extremes() -> None:
    assert rsi([1, 2, 3, 4, 5, 6], 3)[-1] == 100.0  # no losses
    assert rsi([6, 5, 4, 3, 2, 1], 3)[-1] == 0.0  # no gains


def test_true_range_and_atr() -> None:
    high, low, close = [10.0, 12.0, 11.0], [8.0, 9.0, 9.0], [9.0, 11.0, 10.0]
    same(true_range(high, low, close), [2, 3, 2])  # first bar is high - low
    same(atr(high, low, close, 2), [NAN, 2.5, 2.25])


def test_stdev_is_population() -> None:
    same(stdev([2, 4, 4, 4, 5, 5, 7, 9], 8)[-1:], [2.0])  # sqrt(32/8)


def test_bollinger() -> None:
    mid, up, dn = bollinger([2, 4, 4, 4, 5, 5, 7, 9], 8, 2.0)
    same([mid[-1], up[-1], dn[-1]], [5.0, 9.0, 1.0])


def test_highest_lowest() -> None:
    same(highest([1, 3, 2, 5, 4], 3), [NAN, NAN, 3, 5, 5])
    same(lowest([4, 3, 5, 1, 2], 3), [NAN, NAN, 3, 1, 1])


def test_pivots_are_confirmed_late_and_plateau_picks_first_bar() -> None:
    # centre 5 at index 2 is confirmed at index 4 (right = 2)
    same(pivot_high([1, 2, 5, 2, 1], 2, 2), [NAN, NAN, NAN, NAN, 5])
    same(pivot_low([5, 3, 1, 3, 5], 2, 2), [NAN, NAN, NAN, NAN, 1])
    # plateau: the first of two equal highs is the pivot (strict on the left, >= on the right)
    same(pivot_high([1, 5, 5, 2, 1], 1, 1), [NAN, NAN, 5, NAN, NAN])
    same(pivot_low([5, 1, 1, 4, 5], 1, 1), [NAN, NAN, 1, NAN, NAN])
    # no future data: a later higher bar cancels the pivot only after it exists
    same(pivot_high([1, 5, 6], 1, 1), [NAN, NAN, NAN])


def test_vwap_resets_each_utc_day() -> None:
    d1 = datetime(2026, 1, 1, 22, 0, tzinfo=UTC)
    times = [d1, d1 + timedelta(hours=1), d1 + timedelta(hours=2), d1 + timedelta(hours=3)]
    # day 1: bars at 22:00 and 23:00; day 2: bars at 00:00 and 01:00
    out = vwap_daily(times, [10.0, 20.0, 30.0, 50.0], [1.0, 3.0, 2.0, 2.0])
    same(out, [10.0, (10 + 60) / 4, 30.0, (60 + 100) / 4])
    assert isnan(vwap_daily(times[:1], [10.0], [0.0])[0])  # zero volume: no VWAP
