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


EventKey = tuple[str, str, datetime, str]  # symbol, timeframe, bar_close_time, event


def _age_case() -> str:
    from tss.domain.notifier import DEFAULT_MAX_AGE, MAX_AGE

    whens = " ".join(
        f"WHEN '{tf}' THEN make_interval(secs => {int(age.total_seconds())})"
        for tf, age in MAX_AGE.items()
    )
    default = f"make_interval(secs => {int(DEFAULT_MAX_AGE.total_seconds())})"
    return f"CASE timeframe {whens} ELSE {default} END"


async def claim_events(
    session: AsyncSession, now: datetime, events: Collection[str], limit: int
) -> list[tuple[str, str, datetime, str, bool | None]]:
    """Atomically mark up to `limit` unnotified, recent events as notified and return them.

    FOR UPDATE SKIP LOCKED makes concurrent claimers take disjoint rows, so an event can only
    be claimed (and therefore sent) once. Callers must release rows they fail to send.
    """
    from sqlalchemy import text

    sql = text(
        f"""
        UPDATE signal_events SET notified_at = CAST(:now AS timestamptz)
        WHERE (symbol, timeframe, bar_close_time, event) IN (
            SELECT symbol, timeframe, bar_close_time, event FROM signal_events
            WHERE notified_at IS NULL AND event = ANY(:events)
              AND bar_close_time >= CAST(:now AS timestamptz) - ({_age_case()})
            ORDER BY bar_close_time, symbol, timeframe, event
            LIMIT :limit FOR UPDATE SKIP LOCKED
        )
        RETURNING symbol, timeframe, bar_close_time, event, against_htf
        """
    )
    result = await session.execute(sql, {"now": now, "events": list(events), "limit": limit})
    rows = [tuple(r) for r in result.all()]
    rows.sort(key=lambda r: (r[2], r[0], r[1], r[3]))
    return rows


async def release_events(session: AsyncSession, keys: Collection[EventKey]) -> int:
    """Undo a claim for events that were NOT delivered, so they are retried."""
    from sqlalchemy import tuple_, update

    if not keys:
        return 0
    res = await session.execute(
        update(SignalEvent)
        .where(
            tuple_(
                SignalEvent.symbol,
                SignalEvent.timeframe,
                SignalEvent.bar_close_time,
                SignalEvent.event,
            ).in_(list(keys))
        )
        .values(notified_at=None)
    )
    return int(getattr(res, "rowcount", 0) or 0)
