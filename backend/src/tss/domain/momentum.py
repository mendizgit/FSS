"""Movers pool (top 50) and momentum selection (top 20) - Arch §5.3-5.4. Pure functions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MomentumInput:
    symbol: str
    price_change_15m_pct: float | None
    rvol_15m: float | None
    pinned: bool = False


@dataclass(frozen=True)
class MomentumRow:
    symbol: str
    pool_rank: int
    price_change_15m_pct: float | None
    rvol_15m: float | None
    passed_gate2: bool
    selection_rank: int | None
    pinned: bool


def rank_by_rvol(items: list[MomentumInput]) -> list[MomentumInput]:
    """Rankable items (RVOL known) by rvol desc, tie-break |price change| desc, then symbol."""
    rankable = [i for i in items if i.rvol_15m is not None]
    return sorted(
        rankable,
        key=lambda i: (
            -(i.rvol_15m or 0.0),
            -abs(i.price_change_15m_pct or 0.0),
            i.symbol,
        ),
    )


def passes_gate2(item: MomentumInput, min_abs_change: float, min_rvol: float) -> bool:
    if item.price_change_15m_pct is None or item.rvol_15m is None:
        return False
    return abs(item.price_change_15m_pct) >= min_abs_change and item.rvol_15m >= min_rvol


def select_momentum(
    liquid_items: list[MomentumInput],
    pinned_items: list[MomentumInput],
    *,
    pool_size: int,
    top_n: int,
    min_abs_change: float,
    min_rvol: float,
) -> list[MomentumRow]:
    """Pool = top `pool_size` by RVOL among liquid contracts. Gate 2 on the pool, top `top_n`
    by RVOL. Never backfilled. Pinned symbols outside the pool are kept (flagged pinned) with
    their position in the full RVOL ranking when RVOL is known; otherwise they have no row.
    """
    ranking = rank_by_rvol(liquid_items)
    pool = ranking[:pool_size]
    selected = [i for i in pool if passes_gate2(i, min_abs_change, min_rvol)][:top_n]
    selection_rank = {i.symbol: rank for rank, i in enumerate(selected, start=1)}
    pinned_symbols = {i.symbol for i in pinned_items}
    rows = [
        MomentumRow(
            symbol=i.symbol,
            pool_rank=rank,
            price_change_15m_pct=i.price_change_15m_pct,
            rvol_15m=i.rvol_15m,
            passed_gate2=passes_gate2(i, min_abs_change, min_rvol),
            selection_rank=selection_rank.get(i.symbol),
            pinned=i.symbol in pinned_symbols,
        )
        for rank, i in enumerate(pool, start=1)
    ]
    in_pool = {r.symbol for r in rows}
    full_rank = {
        i.symbol: rank
        for rank, i in enumerate(
            rank_by_rvol(
                liquid_items
                + [p for p in pinned_items if p.symbol not in {x.symbol for x in liquid_items}]
            ),
            start=1,
        )
    }
    for p in pinned_items:
        if p.symbol in in_pool or p.symbol not in full_rank:
            continue
        rows.append(
            MomentumRow(
                symbol=p.symbol,
                pool_rank=full_rank[p.symbol],
                price_change_15m_pct=p.price_change_15m_pct,
                rvol_15m=p.rvol_15m,
                passed_gate2=passes_gate2(p, min_abs_change, min_rvol),
                selection_rank=None,
                pinned=True,
            )
        )
    return rows
