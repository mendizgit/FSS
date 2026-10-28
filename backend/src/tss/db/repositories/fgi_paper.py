"""fgi_paper_trades reads and writes."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from tss.db.models.fgi_paper import FgiPaperTrade


async def open_trades(session: AsyncSession) -> list[FgiPaperTrade]:
    stmt = (
        select(FgiPaperTrade)
        .where(FgiPaperTrade.status == "open")
        .order_by(FgiPaperTrade.opened_at)
    )
    return list((await session.execute(stmt)).scalars())


async def closed_pnl(session: AsyncSession) -> float:
    stmt = select(func.coalesce(func.sum(FgiPaperTrade.pnl_usdt), 0.0)).where(
        FgiPaperTrade.status == "closed"
    )
    return float((await session.execute(stmt)).scalar_one() or 0.0)


async def insert_trade(session: AsyncSession, row: dict[str, Any]) -> bool:
    """False when the same signal already has a trade (unique symbol, side, signal time)."""
    stmt = (
        insert(FgiPaperTrade)
        .values(row)
        .on_conflict_do_nothing(constraint="uq_fgi_paper_trade_signal")
        .returning(FgiPaperTrade.id)
    )
    return (await session.execute(stmt)).scalar_one_or_none() is not None


async def all_closed(session: AsyncSession) -> list[FgiPaperTrade]:
    stmt = select(FgiPaperTrade).where(FgiPaperTrade.status == "closed")
    return list((await session.execute(stmt)).scalars())
