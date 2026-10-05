"""news_items repository (Arch §9). Title, URL, source and times only; no article bodies."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from tss.db.models import NewsItem

CHUNK = 200


async def insert_new(session: AsyncSession, rows: list[dict[str, Any]]) -> int:
    """Insert items whose URL is not stored yet (idempotent). Returns how many were new."""
    new = 0
    for i in range(0, len(rows), CHUNK):
        stmt = (
            insert(NewsItem)
            .values(rows[i : i + CHUNK])
            .on_conflict_do_nothing(index_elements=["url"])
            .returning(NewsItem.id)
        )
        new += len((await session.execute(stmt)).all())
    return new


async def list_news(session: AsyncSession, limit: int, symbol: str | None) -> list[NewsItem]:
    """Newest first. Items without a publication time sort by when we fetched them."""
    when = func.coalesce(NewsItem.published_at, NewsItem.fetched_at)
    stmt = select(NewsItem).order_by(when.desc(), NewsItem.id.desc()).limit(limit)
    if symbol:
        stmt = stmt.where(NewsItem.symbols.contains([symbol]))
    return list((await session.execute(stmt)).scalars())


async def newest_published(session: AsyncSession) -> datetime | None:
    return (await session.execute(select(func.max(NewsItem.published_at)))).scalar_one()
