"""F12 Market Movers (UTC day) - Arch §5.6. Runs after every snapshot."""

from __future__ import annotations

import uuid
from datetime import datetime

from tss.agents.base import SKIPPED, AgentResult, BaseAgent
from tss.core.time import floor_to_minutes, utc_date
from tss.db.repositories import contracts as contracts_repo
from tss.db.repositories import discovery as discovery_repo
from tss.db.repositories import market as market_repo
from tss.domain.movers import MoverInput, compute_movers


class MoversAgent(BaseAgent):
    name = "movers"
    critical = False

    async def run(self, cycle_id: uuid.UUID, now: datetime) -> AgentResult:
        ts = floor_to_minutes(now, 5)
        async with self.deps.session_factory() as session:
            contracts = await contracts_repo.active_contracts(session)
            symbols = {c.symbol for c in contracts}
            snaps = [s for s in await market_repo.snapshots_at(session, ts) if s.symbol in symbols]
            opens = await market_repo.daily_opens(session, utc_date(now))
        if not snaps:
            return AgentResult(
                status=SKIPPED, meta={"reason": "no_snapshot_for_ts", "ts": ts.isoformat()}
            )
        if not opens:
            return AgentResult(
                status=SKIPPED, meta={"state": "WAITING_DAY_OPEN", "ts": ts.isoformat()}
            )

        liquid = [s for s in snaps if s.liquid]
        rows = compute_movers(
            [
                MoverInput(
                    s.symbol,
                    s.last_price,
                    opens.get(s.symbol),
                    s.fut_amount24,
                    s.oi_notional_usdt,
                    s.funding_rate,
                )
                for s in liquid
            ],
            self.deps.config.thresholds.movers.top_n,
        )
        records = [
            {
                "ts": ts,
                "side": r.side,
                "rank": r.rank,
                "symbol": r.symbol,
                "day_open": r.day_open,
                "last_price": r.last_price,
                "change_pct": r.change_pct,
                "fut_amount24": r.fut_amount24,
                "oi_notional_usdt": r.oi_notional_usdt,
                "funding_rate": r.funding_rate,
            }
            for r in rows
        ]
        async with self.deps.session_factory() as session:
            await discovery_repo.replace_movers(session, ts, records)
            await session.commit()
        return AgentResult(
            rows_in=len(liquid),
            rows_out=len(records),
            meta={
                "ts": ts.isoformat(),
                "without_open": sum(1 for s in liquid if s.symbol not in opens),
            },
            event="movers_updated",
        )
