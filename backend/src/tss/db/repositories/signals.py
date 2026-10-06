"""signals / signal_events repository (Arch §9)."""

from __future__ import annotations

from collections.abc import Collection
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, literal_column, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from tss.db.models import Signal, SignalEvent, SignalSetup
from tss.domain.setups import (
    EVENT_LOOKBACK,
    EVENTS,
    Setup,
    TfView,
    recent_events,
)


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


async def events_since(
    session: AsyncSession, symbols: Collection[str], events: Collection[str], since: datetime
) -> list[SignalEvent]:
    """Stored events of the given kinds with bar_close_time >= since (newest first)."""
    if not symbols:
        return []
    result = await session.execute(
        select(SignalEvent)
        .where(
            SignalEvent.symbol.in_(list(symbols)),
            SignalEvent.event.in_(list(events)),
            SignalEvent.bar_close_time >= since,
        )
        .order_by(SignalEvent.bar_close_time.desc())
    )
    return list(result.scalars())


async def purge_older_than(session: AsyncSession, cutoff: datetime) -> dict[str, int]:
    signals = await session.execute(delete(Signal).where(Signal.computed_at < cutoff))
    events = await session.execute(delete(SignalEvent).where(SignalEvent.bar_close_time < cutoff))
    return {
        "signals": int(getattr(signals, "rowcount", 0) or 0),
        "signal_events": int(getattr(events, "rowcount", 0) or 0),
    }


async def load_views(session: AsyncSession, symbols: Collection[str]) -> dict[str, list[TfView]]:
    """Newest signal row per timeframe plus its recent events, per symbol (input of classify)."""
    return await views_from_rows(session, await latest_signals(session, symbols))


async def views_from_rows(session: AsyncSession, rows: list[Signal]) -> dict[str, list[TfView]]:
    symbols = {r.symbol for r in rows}
    if not rows:
        return {}
    newest = max(r.bar_close_time for r in rows)
    stored = await events_since(session, symbols, EVENTS, newest - EVENT_LOOKBACK)
    by_key: dict[tuple[str, str], list[tuple[str, datetime, bool | None]]] = {}
    for e in stored:
        by_key.setdefault((e.symbol, e.timeframe), []).append(
            (e.event, e.bar_close_time, e.against_htf)
        )
    out: dict[str, list[TfView]] = {}
    for r in rows:
        events = recent_events(
            r.bar_close_time,
            r.timeframe,
            by_key.get((r.symbol, r.timeframe), []),
            r.last_event,
            r.bars_ago,
            r.against_htf,
        )
        out.setdefault(r.symbol, []).append(
            TfView(r.timeframe, r.bar_close_time, r.m_trend, events)
        )
    return out


async def get_setups(session: AsyncSession) -> dict[str, SignalSetup]:
    return {s.symbol: s for s in (await session.execute(select(SignalSetup))).scalars()}


async def save_setups(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    """Insert or replace whole rows (primary key: symbol)."""
    if not rows:
        return
    stmt = insert(SignalSetup).values(rows)
    update = {c: getattr(stmt.excluded, c) for c in rows[0] if c != "symbol"}
    await session.execute(stmt.on_conflict_do_update(index_elements=["symbol"], set_=update))


def setup_row(
    symbol: str, setup: Setup, now: datetime, *, detected_at: datetime, notified_at: datetime | None
) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "bias": setup.bias,
        "active": True,
        "trigger_timeframe": setup.trigger_timeframe,
        "trigger_event": setup.trigger_event,
        "trigger_bar_close_time": setup.trigger_bar_close_time,
        "against_htf": setup.against_htf,
        "htf_event": setup.htf_event,
        "htf_bars_ago": setup.htf_bars_ago,
        "detected_at": detected_at,
        "notified_at": notified_at,
        "updated_at": now,
    }


async def deactivate_setups(session: AsyncSession, symbols: Collection[str], now: datetime) -> None:
    if symbols:
        await session.execute(
            update(SignalSetup)
            .where(SignalSetup.symbol.in_(list(symbols)))
            .values(active=False, updated_at=now)
        )


async def claim_setups(
    session: AsyncSession, now: datetime, max_age: timedelta, limit: int
) -> list[SignalSetup]:
    """Atomically mark up to `limit` active, unnotified, recent setups as notified and return them.

    FOR UPDATE SKIP LOCKED makes concurrent claimers take disjoint rows (at-most-once delivery).
    Callers release the rows they fail to send.
    """
    chosen = (
        select(SignalSetup.symbol)
        .where(
            SignalSetup.active.is_(True),
            SignalSetup.notified_at.is_(None),
            SignalSetup.detected_at >= now - max_age,
        )
        .order_by(SignalSetup.detected_at, SignalSetup.symbol)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    symbols = list((await session.execute(chosen)).scalars())
    if not symbols:
        return []
    result = await session.execute(
        update(SignalSetup)
        .where(SignalSetup.symbol.in_(symbols), SignalSetup.notified_at.is_(None))
        .values(notified_at=now)
        .returning(SignalSetup)
    )
    rows = list(result.scalars())
    rows.sort(key=lambda r: (r.detected_at, r.symbol))
    return rows


async def release_setups(session: AsyncSession, keys: Collection[tuple[str, datetime]]) -> int:
    """Undo a claim for setups not delivered ((symbol, detected_at) keys); they are retried."""
    n = 0
    for symbol, detected_at in keys:
        res = await session.execute(
            update(SignalSetup)
            .where(SignalSetup.symbol == symbol, SignalSetup.detected_at == detected_at)
            .values(notified_at=None)
        )
        n += int(getattr(res, "rowcount", 0) or 0)
    return n
