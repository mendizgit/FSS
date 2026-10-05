"""momentum_rankings, classifications, market_movers repositories (Arch §9)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from tss.db.models import Classification, MarketMover, MomentumRanking

CHUNK = 500


async def _insert_ignore_dupes_update(
    session: AsyncSession, model: Any, rows: list[dict[str, Any]], keys: list[str]
) -> int:
    for i in range(0, len(rows), CHUNK):
        chunk = rows[i : i + CHUNK]
        stmt = insert(model).values(chunk)
        update = {c: stmt.excluded[c] for c in chunk[0] if c not in keys}
        await session.execute(stmt.on_conflict_do_update(index_elements=keys, set_=update))
    return len(rows)


# --- momentum ----------------------------------------------------------------------------


async def save_momentum(session: AsyncSession, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    return await _insert_ignore_dupes_update(session, MomentumRanking, rows, ["cycle_id", "symbol"])


async def latest_momentum(session: AsyncSession) -> list[MomentumRanking]:
    """Rows of the newest cycle, pool order."""
    newest = (
        select(MomentumRanking.cycle_id)
        .order_by(MomentumRanking.ts.desc())
        .limit(1)
        .scalar_subquery()
    )
    result = await session.execute(
        select(MomentumRanking)
        .where(MomentumRanking.cycle_id == newest)
        .order_by(MomentumRanking.pool_rank)
    )
    return list(result.scalars())


async def selected_symbols(session: AsyncSession, cycle_id: uuid.UUID) -> list[str]:
    result = await session.execute(
        select(MomentumRanking.symbol)
        .where(MomentumRanking.cycle_id == cycle_id, MomentumRanking.selection_rank.is_not(None))
        .order_by(MomentumRanking.selection_rank)
    )
    return list(result.scalars())


# --- classification ----------------------------------------------------------------------


async def save_classifications(session: AsyncSession, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    return await _insert_ignore_dupes_update(
        session, Classification, rows, ["cycle_id", "symbol", "window"]
    )


async def latest_classifications(session: AsyncSession, window: str) -> list[Classification]:
    newest = (
        select(Classification.cycle_id)
        .order_by(Classification.ts.desc())
        .limit(1)
        .scalar_subquery()
    )
    result = await session.execute(
        select(Classification)
        .where(Classification.cycle_id == newest, Classification.window == window)
        .order_by(Classification.symbol)
    )
    return list(result.scalars())


async def classification_history(
    session: AsyncSession, symbol: str, window: str, since: datetime
) -> list[Classification]:
    result = await session.execute(
        select(Classification)
        .where(
            Classification.symbol == symbol,
            Classification.window == window,
            Classification.ts >= since,
        )
        .order_by(Classification.ts)
    )
    return list(result.scalars())


# --- movers ------------------------------------------------------------------------------


async def replace_movers(session: AsyncSession, ts: datetime, rows: list[dict[str, Any]]) -> int:
    """Idempotent per snapshot ts: delete the ts then insert."""
    await session.execute(delete(MarketMover).where(MarketMover.ts == ts))
    for i in range(0, len(rows), CHUNK):
        await session.execute(insert(MarketMover).values(rows[i : i + CHUNK]))
    return len(rows)


async def latest_movers(session: AsyncSession) -> list[MarketMover]:
    newest = select(func.max(MarketMover.ts)).scalar_subquery()
    result = await session.execute(
        select(MarketMover)
        .where(MarketMover.ts == newest)
        .order_by(MarketMover.side, MarketMover.rank)
    )
    return list(result.scalars())


# --- retention ---------------------------------------------------------------------------


async def purge_older_than(session: AsyncSession, cutoff: datetime) -> dict[str, int]:
    counts: dict[str, int] = {}
    for model in (MomentumRanking, Classification, MarketMover):
        res = await session.execute(delete(model).where(model.ts < cutoff))
        counts[model.__tablename__] = int(getattr(res, "rowcount", 0) or 0)
    return counts


def hours_ago(now: datetime, hours: int) -> datetime:
    return now - timedelta(hours=hours)
