"""contracts repository (Arch §9). The 'active' set is the latest universe refresh."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from tss.db.models import Contract, MarketSnapshot

CHUNK = 500


async def upsert_contracts(session: AsyncSession, rows: list[dict[str, Any]]) -> int:
    for i in range(0, len(rows), CHUNK):
        chunk = rows[i : i + CHUNK]
        stmt = insert(Contract).values(chunk)
        update = {c: stmt.excluded[c] for c in chunk[0] if c != "symbol"}
        await session.execute(stmt.on_conflict_do_update(index_elements=["symbol"], set_=update))
    return len(rows)


async def latest_refresh(session: AsyncSession) -> Any:
    return (await session.execute(select(func.max(Contract.updated_at)))).scalar_one()


async def active_contracts(session: AsyncSession) -> list[Contract]:
    """state 0 (enabled), not denylisted, present in the latest universe refresh."""
    refreshed = await latest_refresh(session)
    if refreshed is None:
        return []
    result = await session.execute(
        select(Contract).where(
            Contract.state == 0,
            Contract.denylisted.is_(False),
            Contract.updated_at == refreshed,
        )
    )
    return list(result.scalars())


async def universe_counts(session: AsyncSession) -> dict[str, int]:
    refreshed = await latest_refresh(session)
    if refreshed is None:
        return {"total": 0, "active": 0, "liquid": 0, "denylisted": 0, "zero_fee": 0}
    base = select(Contract).where(Contract.updated_at == refreshed).subquery()
    total = (await session.execute(select(func.count()).select_from(base))).scalar_one()
    active_where = (base.c.state == 0) & (base.c.denylisted.is_(False))
    active = (
        await session.execute(select(func.count()).select_from(base).where(active_where))
    ).scalar_one()
    denylisted = (
        await session.execute(select(func.count()).select_from(base).where(base.c.denylisted))
    ).scalar_one()
    zero_fee = (
        await session.execute(
            select(func.count()).select_from(base).where(active_where & base.c.zero_fee.is_(True))
        )
    ).scalar_one()
    last_ts = (await session.execute(select(func.max(MarketSnapshot.ts)))).scalar_one()
    liquid = 0
    if last_ts is not None:
        liquid = (
            await session.execute(
                select(func.count())
                .select_from(MarketSnapshot)
                .join(base, base.c.symbol == MarketSnapshot.symbol)
                .where(MarketSnapshot.ts == last_ts, MarketSnapshot.liquid.is_(True), active_where)
            )
        ).scalar_one()
    return {
        "total": int(total),
        "active": int(active),
        "liquid": int(liquid),
        "denylisted": int(denylisted),
        "zero_fee": int(zero_fee),
    }


async def contracts_by_symbol(session: AsyncSession, symbols: list[str]) -> dict[str, Contract]:
    if not symbols:
        return {}
    result = await session.execute(select(Contract).where(Contract.symbol.in_(symbols)))
    return {c.symbol: c for c in result.scalars()}
