"""paper_trades reads and writes."""

from __future__ import annotations

from collections.abc import Collection
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from tss.db.models.paper import PaperTrade
from tss.domain import paper as pm


async def open_trades(session: AsyncSession) -> list[PaperTrade]:
    stmt = select(PaperTrade).where(PaperTrade.status == "open").order_by(PaperTrade.opened_at)
    return list((await session.execute(stmt)).scalars())


async def closed_pnl(session: AsyncSession) -> float:
    stmt = select(func.coalesce(func.sum(PaperTrade.pnl_usdt), 0.0)).where(
        PaperTrade.status == "closed"
    )
    return float((await session.execute(stmt)).scalar_one() or 0.0)


async def insert_trade(session: AsyncSession, row: dict[str, Any]) -> bool:
    """False when the same setup already has a trade (unique symbol, side, setup time)."""
    stmt = (
        insert(PaperTrade)
        .values(row)
        .on_conflict_do_nothing(constraint="uq_paper_trade_setup")
        .returning(PaperTrade.id)
    )
    return (await session.execute(stmt)).scalar_one_or_none() is not None


async def known_setups(
    session: AsyncSession, keys: Collection[tuple[str, str, datetime]]
) -> set[tuple[str, str, datetime]]:
    if not keys:
        return set()
    stmt = select(PaperTrade.symbol, PaperTrade.side, PaperTrade.setup_detected_at).where(
        PaperTrade.symbol.in_({k[0] for k in keys})
    )
    found = {(s, b, t) for s, b, t in (await session.execute(stmt)).all()}
    return found & set(keys)


async def blocked_setups(
    session: AsyncSession, keys: Collection[tuple[str, str, datetime]]
) -> set[tuple[str, str, datetime]]:
    """Setups (symbol, side, detected_at) raised while a trade on the symbol was open."""
    if not keys:
        return set()
    stmt = select(PaperTrade.symbol, PaperTrade.opened_at, PaperTrade.closed_at).where(
        PaperTrade.symbol.in_({k[0] for k in keys})
    )
    trades = (await session.execute(stmt)).all()
    return {
        k
        for k in keys
        if any(sym == k[0] and pm.open_at(opened, closed, k[2]) for sym, opened, closed in trades)
    }


async def recent_closed(session: AsyncSession, limit: int) -> list[PaperTrade]:
    stmt = (
        select(PaperTrade)
        .where(PaperTrade.status == "closed")
        .order_by(PaperTrade.closed_at.desc())
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars())


async def all_closed(session: AsyncSession) -> list[PaperTrade]:
    stmt = select(PaperTrade).where(PaperTrade.status == "closed")
    return list((await session.execute(stmt)).scalars())
