"""GET /api/news?limit=50&symbol= (newest first)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from tss.api.deps import get_session
from tss.api.schemas.models import NewsItemOut, NewsOut
from tss.db.repositories import news as news_repo

router = APIRouter()

SYMBOL_PATTERN = r"^[A-Z0-9]{2,32}(_USDT)?$"


@router.get("/news", response_model=NewsOut)
async def news(
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    symbol: Annotated[str | None, Query(pattern=SYMBOL_PATTERN)] = None,
) -> NewsOut:
    """`symbol` accepts a base coin (BTC) or a contract symbol (BTC_USDT)."""
    contract = (
        None if symbol is None else (symbol if symbol.endswith("_USDT") else f"{symbol}_USDT")
    )
    rows = await news_repo.list_news(session, limit, contract)
    return NewsOut(
        symbol=contract,
        items=[
            NewsItemOut(
                id=r.id,
                source=r.source,
                title=r.title,
                url=r.url,
                published_at=r.published_at,
                fetched_at=r.fetched_at,
                symbols=list(r.symbols or []),
            )
            for r in rows
        ],
    )
