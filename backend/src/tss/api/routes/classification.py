"""GET /api/classification/latest and /api/classification/{symbol}/history."""

from __future__ import annotations

from datetime import timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from tss.api.deps import get_session
from tss.api.schemas.models import ClassificationOut, ClassificationRow, HistoryOut, HistoryPoint
from tss.core.time import utc_now
from tss.db.repositories import contracts as contracts_repo
from tss.db.repositories import discovery as discovery_repo
from tss.db.repositories import market as market_repo

router = APIRouter()
Session = Annotated[AsyncSession, Depends(get_session)]
Window = Literal["1h", "4h"]


@router.get("/classification/latest", response_model=ClassificationOut)
async def classification_latest(session: Session, window: Window = "1h") -> ClassificationOut:
    rows = await discovery_repo.latest_classifications(session, window)
    symbols = [r.symbol for r in rows]
    contracts = await contracts_repo.contracts_by_symbol(session, symbols)
    snaps = await market_repo.latest_snapshots(session, symbols)
    momentum = {m.symbol: m for m in await discovery_repo.latest_momentum(session)}
    out = [
        ClassificationRow(
            symbol=r.symbol,
            window=r.window,
            ts=r.ts,
            pinned=bool(contracts[r.symbol].pinned) if r.symbol in contracts else False,
            last_price=snaps[r.symbol].last_price if r.symbol in snaps else None,
            price_change_15m_pct=(
                momentum[r.symbol].price_change_15m_pct if r.symbol in momentum else None
            ),
            price_change_pct=r.price_change_pct,
            oi_notional_usdt=snaps[r.symbol].oi_notional_usdt if r.symbol in snaps else None,
            oi_change_pct=r.oi_change_pct,
            fut_volume_change_pct=r.fut_volume_change_pct,
            spot_volume_change_pct=r.spot_volume_change_pct,
            funding_now=r.funding_now,
            funding_delta=r.funding_delta,
            state=r.state,
            flags=list(r.flags or []),
            unreliable_reasons=list(r.unreliable_reasons or []),
        )
        for r in rows
    ]
    return ClassificationOut(
        window=window,
        cycle_id=rows[0].cycle_id if rows else None,
        ts=rows[0].ts if rows else None,
        rows=out,
    )


@router.get("/classification/{symbol}/history", response_model=HistoryOut)
async def classification_history(
    symbol: str,
    session: Session,
    window: Window = "1h",
    hours: Annotated[int, Query(ge=1, le=120)] = 24,
) -> HistoryOut:
    since = utc_now() - timedelta(hours=hours)
    rows = await discovery_repo.classification_history(session, symbol, window, since)
    return HistoryOut(
        symbol=symbol,
        window=window,
        hours=hours,
        points=[
            HistoryPoint(
                ts=r.ts,
                state=r.state,
                price_change_pct=r.price_change_pct,
                oi_change_pct=r.oi_change_pct,
                fut_volume_change_pct=r.fut_volume_change_pct,
                spot_volume_change_pct=r.spot_volume_change_pct,
                funding_now=r.funding_now,
                funding_delta=r.funding_delta,
                flags=list(r.flags or []),
            )
            for r in rows
        ],
    )
