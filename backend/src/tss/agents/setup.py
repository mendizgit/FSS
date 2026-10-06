"""F10a Setup tracker: keeps signal_setups (latest Long / Short setup per symbol) up to date.

Runs right after every signal run. It decides which setups are NEW (exactly the ones the
Notifier then sends to Telegram); the dashboard tabs use the same rule (domain/setups.py).
Majors are not tracked (they have their own tab and no setup alerts).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from tss.agents.base import SUCCESS, AgentResult, BaseAgent
from tss.db.repositories import signals as signals_repo
from tss.domain.setups import Setup, classify
from tss.realtime.symbols import live_symbols


class SetupAgent(BaseAgent):
    name = "setup"
    critical = False

    async def run(self, cycle_id: uuid.UUID, now: datetime) -> AgentResult:
        majors = set(self.deps.config.thresholds.signals.majors)
        symbols = sorted(await live_symbols(self.deps.session_factory, majors) - majors)
        async with self.deps.session_factory() as session:
            views = await signals_repo.load_views(session, symbols)
            existing = await signals_repo.get_setups(session)
            baseline = not existing  # first ever run: record, do not alert the current setups
            current: dict[str, Setup] = {}
            for symbol in symbols:
                setup = classify(views.get(symbol, []))
                if setup is not None:
                    current[symbol] = setup

            rows: list[dict[str, Any]] = []
            new_alerts = 0
            for symbol, setup in current.items():
                row = existing.get(symbol)
                key = (setup.bias, setup.trigger_timeframe, setup.trigger_bar_close_time)
                if row is None:
                    notified = now if baseline else None
                    rows.append(
                        signals_repo.setup_row(
                            symbol, setup, now, detected_at=now, notified_at=notified
                        )
                    )
                    new_alerts += 0 if baseline else 1
                elif row.active and row.bias == setup.bias:
                    # same setup still holding (the trigger may move to a fresher event): no alert
                    rows.append(
                        signals_repo.setup_row(
                            symbol,
                            setup,
                            now,
                            detected_at=row.detected_at,
                            notified_at=row.notified_at,
                        )
                    )
                elif (row.bias, row.trigger_timeframe, row.trigger_bar_close_time) == key:
                    # back after a gap with the very same trigger event: already alerted
                    rows.append(
                        signals_repo.setup_row(
                            symbol,
                            setup,
                            now,
                            detected_at=row.detected_at,
                            notified_at=row.notified_at,
                        )
                    )
                else:
                    rows.append(
                        signals_repo.setup_row(
                            symbol, setup, now, detected_at=now, notified_at=None
                        )
                    )
                    new_alerts += 1
            gone = [s for s, r in existing.items() if r.active and s not in current]
            await signals_repo.save_setups(session, rows)
            await signals_repo.deactivate_setups(session, gone, now)
            await session.commit()
        longs = sum(1 for s in current.values() if s.bias == "long")
        return AgentResult(
            status=SUCCESS,
            rows_in=len(symbols),
            rows_out=len(current),
            meta={
                "longs": longs,
                "shorts": len(current) - longs,
                "new": new_alerts,
                "ended": len(gone),
                "baseline": baseline,
            },
        )
