"""F2 Snapshot Collector: one futures + one spot ticker call -> market_snapshots (Arch §5.1)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from tss.agents.base import PARTIAL, SUCCESS, AgentResult, BaseAgent
from tss.core.errors import DataSourceError
from tss.core.time import floor_to_minutes
from tss.db.repositories import contracts as contracts_repo
from tss.db.repositories import market as market_repo
from tss.domain.universe import is_liquid, oi_notional_usdt


class SnapshotAgent(BaseAgent):
    name = "snapshot"
    critical = True

    async def run(self, cycle_id: uuid.UUID, now: datetime) -> AgentResult:
        ts = floor_to_minutes(now, 5)
        liq = self.deps.config.thresholds.liquidity
        async with self.deps.session_factory() as session:
            contracts = await contracts_repo.active_contracts(session)
            previous_ts = await market_repo.latest_snapshot_ts(session)
        missed = 0
        if previous_ts is not None and ts > previous_ts:
            missed = max(int((ts - previous_ts).total_seconds() // 300) - 1, 0)
        if missed:
            self.log.warning(
                "missed snapshot tick(s)",
                component=self.name,
                phase="P1",
                op="collect",
                missed_ticks=missed,
                previous_ts=previous_ts.isoformat() if previous_ts else None,
                ts=ts.isoformat(),
            )
        if not contracts:
            raise DataSourceError(
                self.name,
                "P1",
                "collect",
                "no active contracts; universe has not been built",
                {"halt": "universe_empty"},
            )

        tickers = {t.symbol: t for t in await self.deps.futures.tickers()}
        status = SUCCESS
        spot: dict[str, Any] = {}
        try:
            spot = {t.symbol: t for t in await self.deps.spot.tickers_24h()}
        except DataSourceError as exc:  # spot optional: fields stay NULL
            status = PARTIAL
            self.log.warning(
                "spot tickers unavailable",
                component=exc.component,
                phase=exc.phase,
                op=exc.operation,
                error=exc.message,
            )

        rows: list[dict[str, Any]] = []
        no_ticker = 0
        for c in contracts:
            t = tickers.get(c.symbol)
            if t is None:
                no_ticker += 1
                continue
            oi = oi_notional_usdt(t.holdVol, c.contract_size, t.fairPrice)
            s = spot.get(c.spot_symbol) if c.spot_symbol else None
            rows.append(
                {
                    "symbol": c.symbol,
                    "ts": ts,
                    "last_price": t.lastPrice,
                    "fair_price": t.fairPrice,
                    "hold_vol": t.holdVol,
                    "oi_notional_usdt": oi,
                    "funding_rate": t.fundingRate,
                    "fut_volume24": t.volume24,
                    "fut_amount24": t.amount24,
                    "liquid": is_liquid(
                        t.amount24, oi, liq.min_turnover_24h_usdt, liq.min_oi_notional_usdt
                    ),
                    "spot_price": s.lastPrice if s else None,
                    "spot_quote_volume24": s.quoteVolume if s else None,
                }
            )
        if not rows:
            raise DataSourceError(
                self.name, "P1", "collect", "ticker response matched no active contract"
            )
        if no_ticker:
            status = PARTIAL
        async with self.deps.session_factory() as session:
            await market_repo.upsert_snapshots(session, rows)
            await session.commit()
        return AgentResult(
            status=status,
            rows_in=len(contracts),
            rows_out=len(rows),
            meta={
                "ts": ts.isoformat(),
                "liquid": sum(1 for r in rows if r["liquid"]),
                "no_ticker": no_ticker,
                "missed_ticks": missed,
            },
        )
