"""GET /api/discovery/latest."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from tss.api.deps import get_config, get_session
from tss.api.schemas.models import DiscoveryOut, DiscoveryRow
from tss.core.settings import AppConfig
from tss.core.time import utc_date, utc_now
from tss.db.repositories import contracts as contracts_repo
from tss.db.repositories import discovery as discovery_repo
from tss.db.repositories import market as market_repo
from tss.domain.calculations import pct_change

router = APIRouter()


@router.get("/discovery/latest", response_model=DiscoveryOut)
async def discovery_latest(
    session: Annotated[AsyncSession, Depends(get_session)],
    cfg: Annotated[AppConfig, Depends(get_config)],
) -> DiscoveryOut:
    rows = await discovery_repo.latest_momentum(session)
    active = await contracts_repo.active_contracts(session)
    pinned_symbols = [c.symbol for c in active if c.pinned]
    symbols = sorted({r.symbol for r in rows} | set(pinned_symbols))
    contracts = await contracts_repo.contracts_by_symbol(session, symbols)
    snaps = await market_repo.latest_snapshots(session, symbols)
    opens = await market_repo.daily_opens(session, utc_date(utc_now()))
    by_symbol = {r.symbol: r for r in rows}

    def build(symbol: str) -> DiscoveryRow:
        m, s, c = by_symbol.get(symbol), snaps.get(symbol), contracts.get(symbol)
        return DiscoveryRow(
            symbol=symbol,
            zero_fee=c.zero_fee if c else None,
            pinned=bool(c.pinned) if c else False,
            last_price=s.last_price if s else None,
            price_change_15m_pct=m.price_change_15m_pct if m else None,
            rvol_15m=m.rvol_15m if m else None,
            fut_amount24=s.fut_amount24 if s else None,
            oi_notional_usdt=s.oi_notional_usdt if s else None,
            funding_rate=s.funding_rate if s else None,
            utc_day_change_pct=pct_change(s.last_price if s else None, opens.get(symbol)),
            pool_rank=m.pool_rank if m else None,
            passed_gate2=bool(m.passed_gate2) if m else False,
            selection_rank=m.selection_rank if m else None,
        )

    pool_size = cfg.thresholds.momentum.pool_size
    return DiscoveryOut(
        cycle_id=rows[0].cycle_id if rows else None,
        ts=rows[0].ts if rows else None,
        pool=[build(r.symbol) for r in rows if r.pool_rank <= pool_size],
        pinned=[build(s) for s in pinned_symbols],
    )
