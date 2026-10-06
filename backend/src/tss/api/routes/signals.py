"""GET /api/signals/latest: newest signal per symbol x timeframe, grouped for the two tabs."""

from __future__ import annotations

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from tss.api.deps import get_config, get_session
from tss.api.schemas.models import RecentEventOut, SignalRowOut, SignalsOut, SignalSymbolOut
from tss.core.settings import AppConfig
from tss.db.models import SignalEvent
from tss.db.models.signals import TIMEFRAMES
from tss.db.repositories import contracts as contracts_repo
from tss.db.repositories import discovery as discovery_repo
from tss.db.repositories import signals as signals_repo
from tss.domain.notifier import NOTIFY_EVENTS

router = APIRouter()

BAR_SECONDS = {"5m": 300, "15m": 900, "1h": 3600}
EVENT_LOOKBACK = timedelta(hours=11)  # covers 10 bars of the slowest timeframe (1h)
MAX_EVENT_BARS = 20


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
    newest_close = max((r.bar_close_time for r in rows), default=None)
    stored = (
        await signals_repo.recent_events(
            session, symbols, NOTIFY_EVENTS, newest_close - EVENT_LOOKBACK
        )
        if newest_close is not None
        else []
    )
    events_by_key: dict[tuple[str, str], list[SignalEvent]] = {}
    for e in stored:
        events_by_key.setdefault((e.symbol, e.timeframe), []).append(e)
    by_symbol: dict[str, list[SignalRowOut]] = {}
    for r in rows:
        secs = BAR_SECONDS.get(r.timeframe, 300)
        recent: list[RecentEventOut] = []
        for e in events_by_key.get((r.symbol, r.timeframe), []):
            ago = round((r.bar_close_time - e.bar_close_time).total_seconds() / secs)
            if 0 <= ago <= MAX_EVENT_BARS:
                recent.append(
                    RecentEventOut(event=e.event, bars_ago=ago, against_htf=e.against_htf)
                )
        # the newest event is known from the full-history computation even when it was never stored
        # (events are stored only from the 3 newest bars of each run)
        if (
            r.last_event in NOTIFY_EVENTS
            and r.bars_ago is not None
            and r.bars_ago <= MAX_EVENT_BARS
            and not any(e.event == r.last_event and e.bars_ago == r.bars_ago for e in recent)
        ):
            recent.append(
                RecentEventOut(event=r.last_event, bars_ago=r.bars_ago, against_htf=r.against_htf)
            )
        recent.sort(key=lambda e: e.bars_ago)
        by_symbol.setdefault(r.symbol, []).append(
            SignalRowOut(
                timeframe=r.timeframe,
                bar_close_time=r.bar_close_time,
                m_trend=r.m_trend,
                last_event=r.last_event,
                bars_ago=r.bars_ago,
                against_htf=r.against_htf,
                zone_position=r.zone_position,
                price_vs_vwap=r.price_vs_vwap,
                computed_at=r.computed_at,
                recent_events=recent,
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
