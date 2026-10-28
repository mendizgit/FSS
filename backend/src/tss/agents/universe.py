"""F1 Universe Builder: MEXC USDT perpetuals -> contracts (Arch §4)."""

from __future__ import annotations

import uuid
from datetime import datetime

from tss.agents.base import PARTIAL, SUCCESS, AgentResult, BaseAgent
from tss.core.errors import DataSourceError
from tss.db.repositories import contracts as repo
from tss.domain.universe import in_universe, spot_symbol_for, zero_fee


class UniverseAgent(BaseAgent):
    name = "universe"
    critical = True

    async def run(self, cycle_id: uuid.UUID, now: datetime) -> AgentResult:
        cfg = self.deps.config
        quote = cfg.thresholds.universe.quote_asset
        denylist = cfg.denylist
        pinned = set(cfg.thresholds.universe.pinned_symbols)

        details = await self.deps.futures.contract_detail()
        status = SUCCESS
        spot_symbols: set[str] | None = None
        try:
            spot_symbols = {t.symbol for t in await self.deps.spot.tickers_24h()}
        except DataSourceError as exc:  # spot is optional: keep existing mappings, report PARTIAL
            status = PARTIAL
            self.log.warning(
                "spot symbol list unavailable",
                component=exc.component,
                phase=exc.phase,
                op=exc.operation,
                error=exc.message,
            )

        rows = []
        active = 0
        for d in details:
            if d.quoteCoin != quote or d.settleCoin != quote:
                continue
            row = {
                "symbol": d.symbol,
                "base_coin": d.baseCoin,
                "quote_coin": d.quoteCoin,
                "settle_coin": d.settleCoin,
                "contract_size": d.contractSize,
                "state": d.state,
                "maker_fee_rate": d.makerFeeRate,
                "taker_fee_rate": d.takerFeeRate,
                "zero_fee": zero_fee(d.makerFeeRate, d.takerFeeRate),
                "denylisted": denylist.is_denied(d.symbol),
                "pinned": d.symbol in pinned,
                "updated_at": now,
            }
            if spot_symbols is not None:
                row["spot_symbol"] = spot_symbol_for(d.baseCoin, quote, spot_symbols)
            rows.append(row)
            if in_universe(d.quoteCoin, d.settleCoin, d.state, quote, denylist.is_denied(d.symbol)):
                active += 1
        if active == 0:
            raise DataSourceError(
                self.name,
                "P1",
                "build_universe",
                "universe is empty: no enabled USDT contracts in contract/detail",
                {"detail_count": len(details), "halt": "universe_empty"},
            )
        missing_pinned = sorted(pinned - {r["symbol"] for r in rows})
        async with self.deps.session_factory() as session:
            await repo.upsert_contracts(session, rows)
            await session.commit()
        return AgentResult(
            status=status,
            rows_in=len(details),
            rows_out=len(rows),
            meta={"active": active, "missing_pinned": missing_pinned},
        )
