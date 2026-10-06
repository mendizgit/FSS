"""Control Agent (F5): job sequencing, cycle_id, breakers, degraded/halt handling, system_state."""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Callable
from datetime import datetime

from tss.agents.base import (
    FAILED,
    PARTIAL,
    SKIPPED,
    SUCCESS,
    AgentOutcome,
    BaseAgent,
    Deps,
    is_db_unreachable,
)
from tss.agents.classification import ClassificationAgent
from tss.agents.kline_sync import KlineSyncAgent
from tss.agents.momentum import MomentumAgent
from tss.agents.movers import MoversAgent
from tss.agents.news import NewsAgent
from tss.agents.notifier import NotifierAgent
from tss.agents.retention import RetentionAgent
from tss.agents.signal import SignalAgent
from tss.agents.snapshot import SnapshotAgent
from tss.agents.universe import UniverseAgent
from tss.clients.rss import RssClient
from tss.clients.telegram import TelegramClient
from tss.control.breaker import CircuitBreaker
from tss.control.flags import news_on, telegram_on
from tss.control.health import HealthInputs, evaluate
from tss.control.schedule import in_quiet_hours
from tss.core.errors import DataSourceError, StorageError
from tss.core.logging import get_logger
from tss.core.time import utc_now
from tss.db.repositories import market as market_repo
from tss.db.repositories import ops

COMPONENT = "control"
PHASE = "P1"
FUTURES_AGENTS = frozenset({"universe", "snapshot", "kline_sync"})
FUTURES_SOURCE = "mexc_futures"
# retention keeps its own schedule
PAUSABLE_JOBS = frozenset({"universe", "snapshot", "movers", "pipeline", "signal", "news"})
# jobs that need MEXC (directly, or because their input is a MEXC-fed cycle); news uses RSS
MEXC_JOBS = frozenset({"universe", "snapshot", "movers", "pipeline", "signal"})
PROBE_FAILURES = 2  # consecutive failed probes before the system pauses
PROBE_GAP_S = 2.0


class Controller:
    def __init__(
        self,
        deps: Deps,
        rss: RssClient,
        clock: Callable[[], datetime] = utc_now,
        telegram: TelegramClient | None = None,
    ) -> None:
        self.deps = deps
        self.clock = clock
        ccfg = deps.config.thresholds.control
        self.budget_s = ccfg.cycle_budget_s
        self.agents: dict[str, BaseAgent] = {
            a.name: a
            for a in (
                UniverseAgent(deps),
                SnapshotAgent(deps),
                KlineSyncAgent(deps),
                MomentumAgent(deps),
                ClassificationAgent(deps),
                MoversAgent(deps),
                RetentionAgent(deps),
                NewsAgent(deps, rss),
                SignalAgent(deps),
                NotifierAgent(deps, telegram),
            )
        }
        self.breakers = {
            name: CircuitBreaker(ccfg.breaker_failures, ccfg.breaker_cooldown_s)
            for name in (*self.agents, FUTURES_SOURCE)
        }
        self.telegram_enabled = telegram is not None
        self.halt_reason: str | None = None
        self.mexc_down = False
        self.degraded: set[str] = set()
        self._busy: set[str] = set()
        self.log = get_logger(COMPONENT)

    def quiet_now(self) -> bool:
        q = self.deps.config.thresholds.quiet_hours
        return in_quiet_hours(self.clock(), q.pause_hour_ist, q.resume_hour_ist)

    # --- failure policy ------------------------------------------------------------------

    def halt(self, reason: str) -> None:
        if self.halt_reason is None:
            self.log.error(
                "critical halt", component=COMPONENT, phase=PHASE, op="halt", reason=reason
            )
        self.halt_reason = reason

    def _apply_outcome(self, agent: BaseAgent, outcome: AgentOutcome, now: datetime) -> None:
        name = agent.name
        breaker = self.breakers[name]
        if outcome.status in (SUCCESS, PARTIAL, SKIPPED):
            breaker.record_success()
            self.degraded.discard(name)
            if name in FUTURES_AGENTS and outcome.status != SKIPPED:
                self.breakers[FUTURES_SOURCE].record_success()
            if outcome.status == PARTIAL:
                self.degraded.add(name)
            return
        breaker.record_failure(now)
        err = outcome.error
        if err is None:
            return
        if isinstance(err, StorageError):
            self.halt(f"database unreachable ({err.component}/{err.operation})")
        elif err.context.get("halt") == "universe_empty":
            self.halt("universe is empty")
        if err.component == FUTURES_SOURCE:
            source = self.breakers[FUTURES_SOURCE]
            source.record_failure(now)
            if source.is_open(now):
                self.halt("MEXC futures breaker open")
        self.degraded.add(name)

    async def run_agent(
        self, agent: BaseAgent, cycle_id: uuid.UUID, now: datetime, *, bypass: bool = False
    ) -> AgentOutcome | None:
        """Run one agent under the failure policy. None means it was not executed."""
        name = agent.name
        if self.halt_reason and not bypass:
            self.log.warning(
                "skipped: system halted",
                component=COMPONENT,
                phase=PHASE,
                op=name,
                reason=self.halt_reason,
            )
            return None
        if not bypass and not self.breakers[name].allow(now):
            self.log.warning("skipped: breaker open", component=COMPONENT, phase=PHASE, op=name)
            self.degraded.add(name)
            return None
        try:
            outcome = await agent.execute(cycle_id, now)
        except StorageError as exc:
            self.halt(f"database unreachable ({exc.component}/{exc.operation})")
            return None
        self._apply_outcome(agent, outcome, now)
        return outcome

    # --- state ---------------------------------------------------------------------------

    async def refresh_state(self) -> None:
        now = self.clock()
        try:
            async with self.deps.session_factory() as session:
                earliest = await market_repo.earliest_snapshot_overall(session)
                state, reason = evaluate(
                    HealthInputs(
                        halt_reason=self.halt_reason,
                        mexc_down=self.mexc_down,
                        open_breakers=sorted(n for n, b in self.breakers.items() if b.is_open(now)),
                        degraded_agents=sorted(self.degraded),
                        earliest_snapshot=earliest,
                        now=now,
                    )
                )
                if await ops.set_system_state(session, state, reason, now):
                    await ops.notify(
                        session, "system_state", now, {"state": state, "reason": reason}
                    )
                await session.commit()
        except Exception as exc:
            if is_db_unreachable(exc):
                self.halt("database unreachable (control/refresh_state)")
            self.log.error(
                "state refresh failed",
                component=COMPONENT,
                phase=PHASE,
                op="refresh_state",
                error=type(exc).__name__,
            )

    # --- jobs ----------------------------------------------------------------------------

    async def _exclusive(self, job: str, coro_fn: Callable[[], object]) -> None:
        """max_instances=1: a job that is already running is skipped, never doubled."""
        if job in PAUSABLE_JOBS and self.quiet_now():
            return  # daily quiet hours: nothing runs, nothing is logged per tick
        if job in MEXC_JOBS and not await self._mexc_reachable():
            return  # paused until the connection returns (mexc_recovery_job resumes)
        if job in self._busy:
            self.log.warning("job still running; skipped", component=COMPONENT, phase=PHASE, op=job)
            return
        self._busy.add(job)
        try:
            await coro_fn()  # type: ignore[misc]
        finally:
            self._busy.discard(job)
            await self.refresh_state()

    async def _probe_mexc(self) -> bool:
        try:
            await self.deps.futures.ping()
        except DataSourceError as exc:
            self.log.warning(
                "mexc probe failed",
                component=COMPONENT,
                phase=PHASE,
                op="mexc_probe",
                reason=exc.message,
            )
            return False
        return True

    async def _mexc_reachable(self) -> bool:
        """Pre-run gate: PROBE_FAILURES failed probes in a row pause every MEXC job."""
        if self.mexc_down:
            return False
        for attempt in range(PROBE_FAILURES):
            if await self._probe_mexc():
                return True
            if attempt < PROBE_FAILURES - 1:
                await asyncio.sleep(PROBE_GAP_S)
        self.mexc_down = True
        self.log.error(
            "paused: MEXC unreachable", component=COMPONENT, phase=PHASE, op="mexc_probe"
        )
        await self.refresh_state()
        return False

    async def mexc_recovery_job(self) -> None:
        """While paused by the probe: check every 15 s; on success resume and catch up."""
        if not self.mexc_down or not await self._probe_mexc():
            return
        self.mexc_down = False
        self.log.info("resumed: MEXC reachable", component=COMPONENT, phase=PHASE, op="mexc_probe")
        await self.refresh_state()
        await self.snapshot_job()
        await self.pipeline_job()  # also runs the signal job

    async def universe_job(self) -> None:
        async def go() -> None:
            await self.run_agent(self.agents["universe"], uuid.uuid4(), self.clock())

        await self._exclusive("universe", go)

    async def snapshot_job(self) -> None:
        """Snapshot, then Market Movers (F12) with the same timestamp."""

        async def go() -> None:
            cycle = uuid.uuid4()
            now = self.clock()
            outcome = await self.run_agent(self.agents["snapshot"], cycle, now)
            if outcome is not None and outcome.status in (SUCCESS, PARTIAL):
                await self.run_agent(self.agents["movers"], cycle, now)

        await self._exclusive("snapshot", go)

    async def movers_job(self) -> None:
        async def go() -> None:
            await self.run_agent(self.agents["movers"], uuid.uuid4(), self.clock())

        await self._exclusive("movers", go)

    async def pipeline_job(self) -> None:
        """15-minute pipeline: Kline Sync -> Momentum -> Classification, one cycle_id."""

        async def go() -> None:
            cycle = uuid.uuid4()
            now = self.clock()
            started = time.monotonic()
            statuses: dict[str, str] = {}
            for name in ("kline_sync", "momentum", "classification"):
                outcome = await self.run_agent(self.agents[name], cycle, now)
                if outcome is None:
                    statuses[name] = "NOT_RUN"
                    break
                statuses[name] = outcome.status
                if outcome.status in (FAILED, SKIPPED):
                    break  # later steps depend on this one
            elapsed = time.monotonic() - started
            overrun = elapsed > self.budget_s
            if overrun:
                self.log.warning(
                    "cycle budget exceeded",
                    component=COMPONENT,
                    phase=PHASE,
                    op="pipeline",
                    cycle_id=str(cycle),
                    elapsed_s=round(elapsed, 1),
                    budget_s=self.budget_s,
                )
            complete = statuses.get("classification") in (SUCCESS, PARTIAL)
            await self._record_pipeline(cycle, now, statuses, elapsed, overrun, complete)

        await self._exclusive("pipeline", go)
        # the new selection is saved: compute signals now instead of waiting for the next cron
        await self.signal_job()

    async def _record_pipeline(
        self,
        cycle: uuid.UUID,
        now: datetime,
        statuses: dict[str, str],
        elapsed: float,
        overrun: bool,
        complete: bool,
    ) -> None:
        status = (
            SUCCESS
            if complete and all(s == SUCCESS for s in statuses.values())
            else (PARTIAL if complete else FAILED)
        )
        try:
            async with self.deps.session_factory() as session:
                run_id = await ops.start_run(session, "pipeline", cycle, now)
                await ops.finish_run(
                    session,
                    run_id,
                    finished_at=self.clock(),
                    status=status,
                    meta={
                        "steps": statuses,
                        "duration_s": round(elapsed, 2),
                        "overrun": overrun,
                        "budget_s": self.budget_s,
                    },
                )
                if complete:
                    await ops.notify(session, "cycle_complete", now, {"cycle_id": str(cycle)})
                await session.commit()
        except Exception as exc:
            if is_db_unreachable(exc):
                self.halt("database unreachable (control/record_pipeline)")

    async def signal_job(self) -> None:
        async def go() -> None:
            outcome = await self.run_agent(self.agents["signal"], uuid.uuid4(), self.clock())
            s = self.deps.config.settings
            if (
                self.telegram_enabled
                and telegram_on(await self._flags(), s.telegram_configured, s.telegram_paused)
                and outcome is not None
                and outcome.status in (SUCCESS, PARTIAL)
            ):
                # after every signal run (also retries events released by an earlier failure)
                await self.run_agent(self.agents["notifier"], uuid.uuid4(), self.clock())

        await self._exclusive("signal", go)

    async def _flags(self) -> dict[str, bool]:
        try:
            async with self.deps.session_factory() as session:
                return await ops.get_flags(session)
        except Exception as exc:
            if is_db_unreachable(exc):
                self.halt("database unreachable (control/flags)")
            return {}

    async def news_job(self) -> None:
        async def go() -> None:
            if not news_on(await self._flags()):
                return  # stopped from the dashboard
            await self.run_agent(self.agents["news"], uuid.uuid4(), self.clock())

        await self._exclusive("news", go)

    async def retention_job(self) -> None:
        async def go() -> None:
            await self.run_agent(self.agents["retention"], uuid.uuid4(), self.clock())

        await self._exclusive("retention", go)

    async def recovery_job(self) -> None:
        """While HALTED: poll every 60 s by re-running the Universe Builder, which exercises
        the DB and MEXC futures path. Success clears the halt and resets the breakers.
        """
        if not self.halt_reason:
            return
        now = self.clock()
        try:
            async with self.deps.session_factory() as session:
                await ops.ping(session)
        except Exception as exc:
            self.log.warning(
                "recovery: database still unreachable",
                component=COMPONENT,
                phase=PHASE,
                op="recovery",
                error=type(exc).__name__,
            )
            return
        outcome = await self.run_agent(self.agents["universe"], uuid.uuid4(), now, bypass=True)
        if outcome is not None and outcome.status in (SUCCESS, PARTIAL):
            self.log.info(
                "recovered from halt",
                component=COMPONENT,
                phase=PHASE,
                op="recovery",
                previous=self.halt_reason,
            )
            self.halt_reason = None
            for breaker in self.breakers.values():
                breaker.reset()
            self.degraded.clear()
        await self.refresh_state()

    async def startup(self) -> None:
        """Startup sequence (Arch §8): universe -> snapshot (+movers) -> 15-min pipeline."""
        await self.universe_job()
        if self.halt_reason:
            return
        await self.snapshot_job()
        await self.pipeline_job()
        await self.movers_job()  # daily opens now exist; do not wait for the next 5-min tick
        await self.news_job()  # contracts are known, so symbols can be tagged
        await self.signal_job()  # needs the latest selection from the pipeline
