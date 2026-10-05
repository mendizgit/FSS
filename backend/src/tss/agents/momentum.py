"""F3 steps 2-5: Movers Pool (top 50) and Momentum Selection (top 20) - Arch §5.3-5.4."""

from __future__ import annotations

import uuid
from datetime import datetime

from tss.agents.base import SKIPPED, AgentResult, BaseAgent
from tss.agents.common import expected_last_closed, target_symbols
from tss.core.time import floor_to_minutes
from tss.db.repositories import contracts as contracts_repo
from tss.db.repositories import discovery as discovery_repo
from tss.db.repositories import market as market_repo
from tss.domain.calculations import pct_change, rvol
from tss.domain.momentum import MomentumInput, select_momentum


class MomentumAgent(BaseAgent):
    name = "momentum"
    critical = True

    async def run(self, cycle_id: uuid.UUID, now: datetime) -> AgentResult:
        mcfg = self.deps.config.thresholds.momentum
        ts = floor_to_minutes(now, 15)
        expected = expected_last_closed(now)
        async with self.deps.session_factory() as session:
            contracts = await contracts_repo.active_contracts(session)
            snaps = await market_repo.latest_snapshots(session, [c.symbol for c in contracts])
            liquid, pinned = target_symbols(contracts, snaps)
            bars = await market_repo.last_klines(
                session, liquid | pinned, mcfg.rvol_lookback_bars + 1
            )
        if not liquid and not pinned:
            return AgentResult(status=SKIPPED, meta={"reason": "no_liquid_contracts"})

        def build(symbol: str) -> MomentumInput:
            series = bars.get(symbol, [])
            # Stale kline store (sync failed): the newest closed bar is not the expected one.
            if not series or series[-1].open_time != expected:
                return MomentumInput(symbol, None, None, symbol in pinned)
            change = pct_change(series[-1].close, series[-2].close) if len(series) >= 2 else None
            return MomentumInput(
                symbol,
                change,
                rvol([b.amount for b in series], mcfg.rvol_lookback_bars),
                symbol in pinned,
            )

        liquid_items = [build(s) for s in sorted(liquid)]
        pinned_items = [build(s) for s in sorted(pinned)]
        rows = select_momentum(
            liquid_items,
            pinned_items,
            pool_size=mcfg.pool_size,
            top_n=mcfg.top_n,
            min_abs_change=mcfg.min_abs_price_change_15m_pct,
            min_rvol=mcfg.min_rvol,
        )
        records = [
            {
                "cycle_id": cycle_id,
                "symbol": r.symbol,
                "ts": ts,
                "pool_rank": r.pool_rank,
                "price_change_15m_pct": r.price_change_15m_pct,
                "rvol_15m": r.rvol_15m,
                "passed_gate2": r.passed_gate2,
                "selection_rank": r.selection_rank,
                "pinned": r.pinned,
            }
            for r in rows
        ]
        async with self.deps.session_factory() as session:
            await discovery_repo.save_momentum(session, records)
            await session.commit()
        selected = sum(1 for r in rows if r.selection_rank is not None)
        unrankable = sum(1 for i in liquid_items if i.rvol_15m is None)
        return AgentResult(
            rows_in=len(liquid) + len(pinned - liquid),
            rows_out=len(records),
            selected_count=selected,
            meta={
                "pool": min(len(liquid_items) - unrankable, mcfg.pool_size),
                "unrankable": unrankable,
            },
        )
