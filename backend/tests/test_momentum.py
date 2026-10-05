from tss.domain.momentum import MomentumInput, select_momentum

CFG = {"pool_size": 3, "top_n": 2, "min_abs_change": 1.5, "min_rvol": 1.5}


def mi(sym: str, chg: float | None, rv: float | None, pinned: bool = False) -> MomentumInput:
    return MomentumInput(sym, chg, rv, pinned)


def test_pool_ranking_gate_and_never_backfill() -> None:
    liquid = [
        mi("A", 2.0, 5.0),  # passes
        mi("B", 0.5, 4.0),  # rvol ok, change too small -> fails gate
        mi("C", -3.0, 3.0),  # passes (abs change)
        mi("D", 9.0, 2.0),  # outside pool of 3 (4th by rvol) -> excluded
        mi("E", 9.0, None),  # no rvol -> not rankable
    ]
    rows = select_momentum(liquid, [], **CFG)
    assert [r.symbol for r in rows] == ["A", "B", "C"]
    assert [r.pool_rank for r in rows] == [1, 2, 3]
    assert [r.passed_gate2 for r in rows] == [True, False, True]
    assert [r.selection_rank for r in rows] == [1, None, 2]


def test_top_n_cap_and_tie_break() -> None:
    liquid = [mi("A", 2.0, 3.0), mi("B", -4.0, 3.0), mi("C", 2.0, 3.0)]
    rows = select_momentum(liquid, [], pool_size=3, top_n=2, min_abs_change=1.5, min_rvol=1.5)
    # equal rvol: larger |change| first (B), then symbol order (A before C)
    assert [r.symbol for r in rows] == ["B", "A", "C"]
    assert [r.selection_rank for r in rows] == [1, 2, None]  # top_n = 2


def test_fewer_than_top_n_qualify_is_not_backfilled() -> None:
    liquid = [mi("A", 0.1, 9.0), mi("B", 0.2, 8.0)]
    rows = select_momentum(liquid, [], **CFG)
    assert all(r.selection_rank is None for r in rows)


def test_pinned_outside_pool_keeps_full_rank_and_flag() -> None:
    liquid = [mi("A", 2.0, 9.0), mi("B", 2.0, 8.0), mi("C", 2.0, 7.0), mi("BTC", 0.1, 1.0, True)]
    pinned = [mi("BTC", 0.1, 1.0, True), mi("ETH", 0.1, None, True)]
    rows = select_momentum(liquid, pinned, **CFG)
    btc = next(r for r in rows if r.symbol == "BTC")
    assert btc.pinned and btc.pool_rank == 4 and btc.selection_rank is None
    assert all(r.symbol != "ETH" for r in rows)  # no rvol -> no row (pool_rank is NOT NULL)


def test_pinned_in_pool_can_qualify_on_merit() -> None:
    liquid = [mi("BTC", 2.0, 9.0, True), mi("A", 2.0, 8.0)]
    rows = select_momentum(liquid, [mi("BTC", 2.0, 9.0, True)], **CFG)
    btc = next(r for r in rows if r.symbol == "BTC")
    assert btc.pinned and btc.selection_rank == 1 and btc.pool_rank == 1
