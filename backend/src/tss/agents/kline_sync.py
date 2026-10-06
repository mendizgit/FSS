"""F3 step 1: Kline Sync (Arch §5.2). Closed bars only; also writes daily_opens."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from typing import Any

from tss.agents.base import PARTIAL, SKIPPED, SUCCESS, AgentResult, BaseAgent
from tss.agents.common import target_symbols
from tss.clients.models import Kline
from tss.core.errors import DataSourceError
from tss.core.time import floor_to_minutes, utc_date, utc_day_start
from tss.db.repositories import contracts as contracts_repo
from tss.db.repositories import market as market_repo
from tss.domain.calculations import BAR, is_closed

CONCURRENCY = 5  # the shared rate limiter still spaces the requests
ABORT_AFTER_TRANSPORT_FAILURES = 5  # consecutive connect/timeout failures: stop sending requests


class KlineSyncAgent(BaseAgent):
    name = "kline_sync"
    critical = True

    async def run(self, cycle_id: uuid.UUID, now: datetime) -> AgentResult:
        cfg = self.deps.config
        kcfg = cfg.thresholds.kline
        async with self.deps.session_factory() as session:
            contracts = await contracts_repo.active_contracts(session)
            snaps = await market_repo.latest_snapshots(session, [c.symbol for c in contracts])
            liquid, pinned = target_symbols(contracts, snaps)
            targets = sorted(liquid | pinned)
            latest = await market_repo.latest_kline_open_times(session, targets)
        if not snaps:
            return AgentResult(status=SKIPPED, meta={"reason": "no_snapshots_yet"})
        if not targets:
            return AgentResult(status=SKIPPED, meta={"reason": "no_liquid_contracts"})

        backfill_from = floor_to_minutes(now, 15) - kcfg.backfill_bars * BAR
        sem = asyncio.Semaphore(CONCURRENCY)
        fetched: dict[str, list[Kline]] = {}
        failed: dict[str, str] = {}
        transport_streak = 0  # consecutive failures with no HTTP status (connect/timeout)

        async def fetch(symbol: str) -> None:
            nonlocal transport_streak
            start = latest.get(symbol, backfill_from)  # re-fetch the newest stored bar (+1)
            async with sem:
                if transport_streak >= ABORT_AFTER_TRANSPORT_FAILURES:
                    failed[symbol] = "skipped: MEXC unreachable (consecutive connect failures)"
                    return
                try:
                    fetched[symbol] = await self.deps.futures.klines(
                        symbol, kcfg.interval, start, now
                    )
                    transport_streak = 0
                except DataSourceError as exc:
                    failed[symbol] = exc.message
                    transport_streak = (
                        transport_streak + 1 if exc.context.get("status") is None else 0
                    )

        await asyncio.gather(*(fetch(s) for s in targets))
        if len(failed) == len(targets):
            raise DataSourceError(
                self.name,
                "P1",
                "fetch_klines",
                f"all {len(targets)} kline requests failed; first: {next(iter(failed.values()))}",
            )

        day_start = utc_day_start(now)
        rows: list[dict[str, Any]] = []
        opens: dict[str, float] = {}
        for symbol, bars in fetched.items():
            for bar in bars:
                if bar.open_time == day_start:  # the 00:00 UTC bar (may still be forming)
                    opens[symbol] = bar.open
                if is_closed(bar.open_time, now):
                    rows.append(
                        {
                            "symbol": symbol,
                            "open_time": bar.open_time,
                            "open": bar.open,
                            "high": bar.high,
                            "low": bar.low,
                            "close": bar.close,
                            "volume": bar.volume,
                            "amount": bar.amount,
                        }
                    )

        today = utc_date(now)
        async with self.deps.session_factory() as session:
            await market_repo.upsert_klines(session, rows)
            known = await market_repo.daily_opens(session, today)
            need = [s for s in targets if s not in known and s not in opens]
            stored_bars = await market_repo.klines_at(session, need, day_start)
            for symbol, stored in stored_bars.items():
                opens[symbol] = stored.open  # day open from the stored 00:00 bar
            open_rows = [
                {"symbol": s, "utc_date": today, "open": o}
                for s, o in opens.items()
                if s not in known
            ]
            await market_repo.upsert_daily_opens(session, open_rows)
            await session.commit()

        status = PARTIAL if failed else SUCCESS
        if failed:
            self.log.warning(
                "kline requests failed",
                component=self.name,
                phase="P1",
                op="fetch_klines",
                failed=len(failed),
                sample=sorted(failed)[:5],
            )
        return AgentResult(
            status=status,
            rows_in=len(targets),
            rows_out=len(rows),
            meta={
                "symbols": len(targets),
                "failed": sorted(failed)[:20],
                "daily_opens": len(open_rows),
            },
        )
