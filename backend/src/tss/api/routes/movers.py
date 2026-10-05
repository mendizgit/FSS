"""GET /api/movers/latest."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from tss.api.deps import get_session
from tss.api.schemas.models import MoverRowOut, MoversOut
from tss.core.time import utc_date, utc_now
from tss.db.models import MarketMover
from tss.db.repositories import discovery as discovery_repo
from tss.db.repositories import market as market_repo

router = APIRouter()


def _row(m: MarketMover) -> MoverRowOut:
    return MoverRowOut(
        rank=m.rank,
        symbol=m.symbol,
        day_open=m.day_open,
        last_price=m.last_price,
        change_pct=m.change_pct,
        fut_amount24=m.fut_amount24,
        oi_notional_usdt=m.oi_notional_usdt,
        funding_rate=m.funding_rate,
    )


@router.get("/movers/latest", response_model=MoversOut)
async def movers_latest(session: Annotated[AsyncSession, Depends(get_session)]) -> MoversOut:
    rows = await discovery_repo.latest_movers(session)
    if not rows:
        opens = await market_repo.daily_opens(session, utc_date(utc_now()))
        return MoversOut(
            status="NO_DATA" if opens else "WAITING_DAY_OPEN", ts=None, gainers=[], losers=[]
        )
    return MoversOut(
        status="OK",
        ts=rows[0].ts,
        gainers=[_row(r) for r in rows if r.side == "GAINER"],
        losers=[_row(r) for r in rows if r.side == "LOSER"],
    )
