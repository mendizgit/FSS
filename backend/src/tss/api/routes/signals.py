"""GET /api/signals/latest: newest signal per symbol x timeframe, grouped for the two tabs."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from tss.api.deps import get_config, get_session
from tss.api.schemas.models import SignalRowOut, SignalsOut, SignalSymbolOut
from tss.core.settings import AppConfig
from tss.db.models.signals import TIMEFRAMES
from tss.db.repositories import contracts as contracts_repo
from tss.db.repositories import discovery as discovery_repo
from tss.db.repositories import signals as signals_repo

router = APIRouter()


@router.get("/signals/latest", response_model=SignalsOut)
async def signals_latest(
    session: Annotated[AsyncSession, Depends(get_session)],
    cfg: Annotated[AppConfig, Depends(get_config)],
) -> SignalsOut:
    majors = list(cfg.thresholds.signals.majors)
    momentum = await discovery_repo.latest_momentum(session)
    ranks = {m.symbol: m.selection_rank for m in momentum if m.selection_rank is not None}
    active = await contracts_repo.active_contracts(session)
    pinned = {c.symbol for c in active if c.pinned}
    symbols = set(ranks) | pinned | (set(majors) & {c.symbol for c in active})
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
            group="majors" if symbol in majors else "momentum",
            pinned=symbol in pinned,
            selection_rank=ranks.get(symbol),
            rows=sorted(items, key=lambda x: order.get(x.timeframe, 99)),
        )
        for symbol, items in by_symbol.items()
    ]

    def sort_key(s: SignalSymbolOut) -> tuple[int, int, str]:
        if s.group == "majors":
            return (0, majors.index(s.symbol), s.symbol)  # configured order
        return (1, s.selection_rank if s.selection_rank is not None else 999, s.symbol)

    out.sort(key=sort_key)
    newest = max((r.computed_at for r in rows), default=None)
    return SignalsOut(updated_at=newest, symbols=out)
