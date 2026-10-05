"""signals / signal_events repository (Arch §9)."""

from __future__ import annotations

from collections.abc import Collection
from datetime import datetime
from typing import Any

from sqlalchemy import delete, func, literal_column, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from tss.db.models import Signal, SignalEvent


async def upsert_signals(session: AsyncSession, rows: list[dict[str, Any]]) -> int:
    """Insert or update by (symbol, timeframe, bar_close_time). Returns how many were NEW."""
    if not rows:
        return 0
    base = insert(Signal).values(rows)
    update = {
        c: base.excluded[c] for c in rows[0] if c not in ("symbol", "timeframe", "bar_close_time")
    }
    stmt: Any = base.on_conflict_do_update(
        index_elements=["symbol", "timeframe", "bar_close_time"], set_=update
    ).returning(literal_column("(xmax = 0)"))
    return sum(1 for (inserted,) in (await session.execute(stmt)).all() if inserted)


async def insert_events(
    session: AsyncSession, rows: list[dict[str, Any]]
) -> list[tuple[str, str, datetime, str]]:
    """Idempotent insert; returns only the events that were new."""
    if not rows:
        return []
    stmt = (
        insert(SignalEvent)
        .values(rows)
        .on_conflict_do_nothing(index_elements=["symbol", "timeframe", "bar_close_time", "event"])
        .returning(
            SignalEvent.symbol, SignalEvent.timeframe, SignalEvent.bar_close_time, SignalEvent.event
        )
    )
    return [tuple(r) for r in (await session.execute(stmt)).all()]  # type: ignore[misc]


async def latest_signals(session: AsyncSession, symbols: Collection[str]) -> list[Signal]:
    """Newest row per (symbol, timeframe) for the given symbols."""
    if not symbols:
        return []
    ranked = (
        select(
            Signal.symbol.label("symbol"),
            Signal.timeframe.label("timeframe"),
            Signal.bar_close_time.label("bar_close_time"),
            func.row_number()
            .over(
                partition_by=(Signal.symbol, Signal.timeframe),
                order_by=Signal.bar_close_time.desc(),
            )
            .label("rn"),
        )
        .where(Signal.symbol.in_(list(symbols)))
        .subquery()
    )
    result = await session.execute(
        select(Signal)
        .join(
            ranked,
            (ranked.c.symbol == Signal.symbol)
            & (ranked.c.timeframe == Signal.timeframe)
            & (ranked.c.bar_close_time == Signal.bar_close_time),
        )
        .where(ranked.c.rn == 1)
        .order_by(Signal.symbol, Signal.timeframe)
    )
    return list(result.scalars())


async def purge_older_than(session: AsyncSession, cutoff: datetime) -> dict[str, int]:
    signals = await session.execute(delete(Signal).where(Signal.computed_at < cutoff))
    events = await session.execute(delete(SignalEvent).where(SignalEvent.bar_close_time < cutoff))
    return {
        "signals": int(getattr(signals, "rowcount", 0) or 0),
        "signal_events": int(getattr(events, "rowcount", 0) or 0),
    }
