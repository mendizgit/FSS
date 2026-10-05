"""market_snapshots, klines_15m, daily_opens repositories (Arch §9)."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Collection
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from tss.db.models import DailyOpen, Kline15m, MarketSnapshot

CHUNK = 500


async def _bulk_upsert(
    session: AsyncSession, model: Any, rows: list[dict[str, Any]], keys: list[str]
) -> int:
    for i in range(0, len(rows), CHUNK):
        chunk = rows[i : i + CHUNK]
        stmt = insert(model).values(chunk)
        update = {c: stmt.excluded[c] for c in chunk[0] if c not in keys}
        await session.execute(stmt.on_conflict_do_update(index_elements=keys, set_=update))
    return len(rows)


# --- snapshots ---------------------------------------------------------------------------


async def upsert_snapshots(session: AsyncSession, rows: list[dict[str, Any]]) -> int:
    return await _bulk_upsert(session, MarketSnapshot, rows, ["symbol", "ts"])


async def latest_snapshot_ts(session: AsyncSession) -> datetime | None:
    return (await session.execute(select(func.max(MarketSnapshot.ts)))).scalar_one()


async def snapshots_at(session: AsyncSession, ts: datetime) -> list[MarketSnapshot]:
    result = await session.execute(select(MarketSnapshot).where(MarketSnapshot.ts == ts))
    return list(result.scalars())


async def latest_snapshots(
    session: AsyncSession, symbols: Collection[str]
) -> dict[str, MarketSnapshot]:
    """Newest snapshot per symbol."""
    if not symbols:
        return {}
    ranked = (
        select(
            MarketSnapshot,
            func.row_number()
            .over(partition_by=MarketSnapshot.symbol, order_by=MarketSnapshot.ts.desc())
            .label("rn"),
        )
        .where(MarketSnapshot.symbol.in_(list(symbols)))
        .subquery()
    )
    result = await session.execute(
        select(MarketSnapshot).join(
            ranked,
            (ranked.c.symbol == MarketSnapshot.symbol)
            & (ranked.c.ts == MarketSnapshot.ts)
            & (ranked.c.rn == 1),
        )
    )
    return {s.symbol: s for s in result.scalars()}


async def snapshot_history(
    session: AsyncSession, symbols: Collection[str], since: datetime
) -> dict[str, list[MarketSnapshot]]:
    """Snapshots with ts >= since, oldest first, grouped by symbol."""
    out: dict[str, list[MarketSnapshot]] = defaultdict(list)
    if not symbols:
        return out
    result = await session.execute(
        select(MarketSnapshot)
        .where(MarketSnapshot.symbol.in_(list(symbols)), MarketSnapshot.ts >= since)
        .order_by(MarketSnapshot.symbol, MarketSnapshot.ts)
    )
    for snap in result.scalars():
        out[snap.symbol].append(snap)
    return out


async def earliest_snapshot_ts(
    session: AsyncSession, symbols: Collection[str]
) -> dict[str, datetime]:
    if not symbols:
        return {}
    result = await session.execute(
        select(MarketSnapshot.symbol, func.min(MarketSnapshot.ts))
        .where(MarketSnapshot.symbol.in_(list(symbols)))
        .group_by(MarketSnapshot.symbol)
    )
    return {sym: ts for sym, ts in result.all()}


async def earliest_snapshot_overall(session: AsyncSession) -> datetime | None:
    return (await session.execute(select(func.min(MarketSnapshot.ts)))).scalar_one()


# --- klines ------------------------------------------------------------------------------


async def upsert_klines(session: AsyncSession, rows: list[dict[str, Any]]) -> int:
    return await _bulk_upsert(session, Kline15m, rows, ["symbol", "open_time"])


async def latest_kline_open_times(
    session: AsyncSession, symbols: Collection[str]
) -> dict[str, datetime]:
    if not symbols:
        return {}
    result = await session.execute(
        select(Kline15m.symbol, func.max(Kline15m.open_time))
        .where(Kline15m.symbol.in_(list(symbols)))
        .group_by(Kline15m.symbol)
    )
    return {sym: ts for sym, ts in result.all()}


async def last_klines(
    session: AsyncSession, symbols: Collection[str], limit: int
) -> dict[str, list[Kline15m]]:
    """Newest `limit` stored (closed) bars per symbol, oldest first."""
    out: dict[str, list[Kline15m]] = defaultdict(list)
    if not symbols:
        return out
    ranked = (
        select(
            Kline15m.symbol.label("symbol"),
            Kline15m.open_time.label("open_time"),
            func.row_number()
            .over(partition_by=Kline15m.symbol, order_by=Kline15m.open_time.desc())
            .label("rn"),
        )
        .where(Kline15m.symbol.in_(list(symbols)))
        .subquery()
    )
    result = await session.execute(
        select(Kline15m)
        .join(
            ranked,
            (ranked.c.symbol == Kline15m.symbol) & (ranked.c.open_time == Kline15m.open_time),
        )
        .where(ranked.c.rn <= limit)
        .order_by(Kline15m.symbol, Kline15m.open_time)
    )
    for bar in result.scalars():
        out[bar.symbol].append(bar)
    return out


async def klines_at(
    session: AsyncSession, symbols: Collection[str], open_time: datetime
) -> dict[str, Kline15m]:
    if not symbols:
        return {}
    result = await session.execute(
        select(Kline15m).where(Kline15m.symbol.in_(list(symbols)), Kline15m.open_time == open_time)
    )
    return {k.symbol: k for k in result.scalars()}


# --- daily opens -------------------------------------------------------------------------


async def upsert_daily_opens(session: AsyncSession, rows: list[dict[str, Any]]) -> int:
    return await _bulk_upsert(session, DailyOpen, rows, ["symbol", "utc_date"])


async def daily_opens(session: AsyncSession, utc_date: date) -> dict[str, float]:
    result = await session.execute(select(DailyOpen).where(DailyOpen.utc_date == utc_date))
    return {d.symbol: d.open for d in result.scalars()}


# --- retention ---------------------------------------------------------------------------


async def purge_snapshots(session: AsyncSession, cutoff: datetime) -> int:
    res = await session.execute(delete(MarketSnapshot).where(MarketSnapshot.ts < cutoff))
    return int(getattr(res, "rowcount", 0) or 0)


async def purge_klines(session: AsyncSession, cutoff: datetime, keep_bars: int) -> int:
    """Delete bars older than cutoff, but always keep each symbol's newest `keep_bars`."""
    res = await session.execute(
        text(
            """
            DELETE FROM klines_15m k USING (
                SELECT symbol, open_time,
                       row_number() OVER (PARTITION BY symbol ORDER BY open_time DESC) AS rn
                FROM klines_15m
            ) r
            WHERE k.symbol = r.symbol AND k.open_time = r.open_time
              AND k.open_time < :cutoff AND r.rn > :keep
            """
        ),
        {"cutoff": cutoff, "keep": keep_bars},
    )
    return int(getattr(res, "rowcount", 0) or 0)


async def purge_daily_opens(session: AsyncSession, cutoff_date: date) -> int:
    res = await session.execute(delete(DailyOpen).where(DailyOpen.utc_date < cutoff_date))
    return int(getattr(res, "rowcount", 0) or 0)


def retention_cutoff(now: datetime, days: int) -> datetime:
    return now - timedelta(days=days)
