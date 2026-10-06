from datetime import UTC, datetime, timedelta

import pytest

from tss.indicators.fgi_v3 import Bars
from tss.indicators.heikin_ashi import heikin_ashi


def _bars() -> Bars:
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    return Bars(
        open_time=[t0 + timedelta(minutes=5 * i) for i in range(3)],
        open=[10.0, 12.0, 11.0],
        high=[14.0, 15.0, 12.0],
        low=[9.0, 10.0, 8.0],
        close=[12.0, 11.0, 9.0],
        volume=[1.0, 2.0, 3.0],
    )


def test_hand_computed() -> None:
    ha = heikin_ashi(_bars())
    assert ha.close == pytest.approx([11.25, 12.0, 10.0])
    assert ha.open == pytest.approx([11.0, 11.125, 11.5625])
    assert ha.high == pytest.approx([14.0, 15.0, 12.0])
    assert ha.low == pytest.approx([9.0, 10.0, 8.0])


def test_passthrough_and_invariants() -> None:
    src = _bars()
    ha = heikin_ashi(src)
    assert ha.open_time == src.open_time
    assert ha.volume == src.volume
    for i in range(len(ha)):
        assert ha.high[i] >= max(ha.open[i], ha.close[i])
        assert ha.low[i] <= min(ha.open[i], ha.close[i])
