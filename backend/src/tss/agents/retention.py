"""F11 Retention: daily purge of rows older than RETENTION_DAYS (Arch §9)."""

from __future__ import annotations

import uuid
from datetime import datetime

from tss.agents.base import AgentResult, BaseAgent
from tss.core.time import utc_date
from tss.db.repositories import discovery as discovery_repo
from tss.db.repositories import market as market_repo
from tss.db.repositories import ops
from tss.db.repositories import signals as signals_repo


class RetentionAgent(BaseAgent):
    name = "retention"
    critical = False

    async def run(self, cycle_id: uuid.UUID, now: datetime) -> AgentResult:
        cfg = self.deps.config
        cutoff = market_repo.retention_cutoff(now, cfg.settings.retention_days)
        async with self.deps.session_factory() as session:
            deleted: dict[str, int] = {
                "market_snapshots": await market_repo.purge_snapshots(session, cutoff),
                "klines_15m": await market_repo.purge_klines(
                    session, cutoff, cfg.thresholds.kline.backfill_bars
                ),
                "daily_opens": await market_repo.purge_daily_opens(session, utc_date(cutoff)),
            }
            deleted.update(await discovery_repo.purge_older_than(session, cutoff))
            deleted.update(await ops.purge_ops(session, cutoff))
            deleted.update(await signals_repo.purge_older_than(session, cutoff))
            await session.commit()
        return AgentResult(rows_out=sum(deleted.values()), meta={"deleted": deleted})
