"""GET /api/signals/latest: newest signal per symbol x timeframe for the live symbols."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from tss.api.deps import get_session
from tss.api.schemas.models import SignalRowOut, SignalsOut, SignalSymbolOut
from tss.db.models.signals import TIMEFRAMES
from tss.db.repositories import contracts as contracts_repo
from tss.db.repositories import discovery as discovery_repo
from tss.db.repositories import signals as signals_repo

router = APIRouter()


@router.get("/signals/latest", response_model=SignalsOut)
async def signals_latest(session: Annotated[AsyncSession, Depends(get_session)]) -> SignalsOut:
    momentum = await discovery_repo.latest_momentum(session)
    ranks = {m.symbol: m.selection_rank for m in momentum if m.selection_rank is not None}
    pinned = {c.symbol for c in await contracts_repo.active_contracts(session) if c.pinned}
    symbols = set(ranks) | pinned
    rows = await signals_repo.latest_signals(session, symbols)
    by_symbol: dict[str, list[SignalRowOut]] = {}
    for r in rows:
        by_symbol.setdefault(r.symbol, []).append(
            SignalRowOut(
                timeframe=r.timeframe,
                bar_close_time=r.bar_close_time,
                m_trend=r.m_trend,
                last_event=r.last_event,
                bars_ago=r.bars_ago,
                against_htf=r.against_htf,
                htf_supertrend=r.htf_supertrend,
                local_supertrend=r.local_supertrend,
                consolidated_trend=r.consolidated_trend,
                long_score=r.long_score,
                short_score=r.short_score,
                long_grade=r.long_grade,
                short_grade=r.short_grade,
                rsi_divergence=r.rsi_divergence,
                sr_letter=r.sr_letter,
                zone_position=r.zone_position,
                price_vs_vwap=r.price_vs_vwap,
                computed_at=r.computed_at,
            )
        )
    order = {tf: i for i, tf in enumerate(TIMEFRAMES)}
    out = [
        SignalSymbolOut(
            symbol=symbol,
            pinned=symbol in pinned,
            selection_rank=ranks.get(symbol),
            rows=sorted(items, key=lambda x: order.get(x.timeframe, 99)),
        )
        for symbol, items in by_symbol.items()
    ]
    # pinned (context) first, then by selection rank
    out.sort(
        key=lambda s: (
            not s.pinned,
            s.selection_rank if s.selection_rank is not None else 999,
            s.symbol,
        )
    )
    newest = max((r.computed_at for r in rows), default=None)
    return SignalsOut(updated_at=newest, symbols=out)
