"""F10a Entry tracker: keeps signal_setups (latest 15m Long / Short entry per symbol) up to date.

Runs right after every signal run. It decides which entries are NEW (exactly the ones the
Notifier then sends to Telegram): an alert needs a rising edge (the entry was not active on the
previous run) and at most one alert per symbol and side within the cooldown. The dashboard tabs
use the same rule (domain/setups.py). Majors are not tracked (own tab, no alerts).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any

from tss.agents.base import SUCCESS, AgentResult, BaseAgent
from tss.db.repositories import signals as signals_repo
from tss.domain.setups import Setup, classify
from tss.realtime.symbols import live_symbols


class SetupAgent(BaseAgent):
    name = "setup"
    critical = False

    async def run(self, cycle_id: uuid.UUID, now: datetime) -> AgentResult:
        scfg = self.deps.config.thresholds.signals
        majors = set(scfg.majors)
        cooldown = timedelta(minutes=scfg.alert_cooldown_minutes)
        symbols = sorted(await live_symbols(self.deps.session_factory, majors) - majors)
        async with self.deps.session_factory() as session:
            views = await signals_repo.load_views(session, symbols)
            existing = await signals_repo.get_setups(session)
            # first run of the entry rule: record the current entries, do not alert them
            baseline = not any(r.score is not None for r in existing.values())
            current: dict[str, Setup] = {}
            for symbol in symbols:
                setup = classify(views.get(symbol, []))
                if setup is not None:
                    current[symbol] = setup

            rows: list[dict[str, Any]] = []
            new_alerts = 0
            for symbol, setup in current.items():
                row = existing.get(symbol)
                last_long = row.last_long_alert_at if row else None
                last_short = row.last_short_alert_at if row else None
                if row is not None and row.active and row.bias == setup.bias:
                    # entry still holding (a newer 15m bar may back it): no alert
                    detected_at, notified_at = row.detected_at, row.notified_at
                else:
                    # rising edge: new, back after a gap, or the other side
                    last = last_long if setup.bias == "long" else last_short
                    cooled = last is None or now - last >= cooldown
                    detected_at = now
                    if baseline or not cooled:
                        notified_at = now  # recorded, never alerted
                    else:
                        notified_at = None
                        new_alerts += 1
                        if setup.bias == "long":
                            last_long = now
                        else:
                            last_short = now
                rows.append(
                    signals_repo.setup_row(
                        symbol,
                        setup,
                        now,
                        detected_at=detected_at,
                        notified_at=notified_at,
                        last_long_alert_at=last_long,
                        last_short_alert_at=last_short,
                    )
                )
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
