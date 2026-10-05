import pytest

from tss.domain.movers import MoverInput, compute_movers


def test_gainers_losers_and_skips() -> None:
    items = [
        MoverInput("A", 110.0, 100.0),  # +10 %
        MoverInput("B", 95.0, 100.0),  # -5 %
        MoverInput("C", 101.0, 100.0),  # +1 %
        MoverInput("D", 50.0, None),  # no open -> skipped
        MoverInput("E", None, 100.0),  # no price -> skipped
        MoverInput("F", 70.0, 100.0),  # -30 %
    ]
    rows = compute_movers(items, top_n=2)
    gainers = [r for r in rows if r.side == "GAINER"]
    losers = [r for r in rows if r.side == "LOSER"]
    assert [(r.symbol, r.rank) for r in gainers] == [("A", 1), ("C", 2)]
    assert [(r.symbol, r.rank) for r in losers] == [("F", 1), ("B", 2)]
    assert gainers[0].change_pct == pytest.approx(10.0)
    assert losers[0].change_pct == pytest.approx(-30.0)


def test_no_opens_gives_empty() -> None:
    assert compute_movers([MoverInput("A", 1.0, None)], top_n=10) == []
