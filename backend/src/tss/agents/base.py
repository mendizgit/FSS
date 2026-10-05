"""BaseAgent: owns agent_runs, timing, error wrapping and NOTIFY (skills/market-data-agents)."""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, ClassVar

from sqlalchemy.exc import DBAPIError, InterfaceError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tss.clients.mexc_futures import MexcFuturesClient
from tss.clients.mexc_spot import MexcSpotClient
from tss.core.errors import StorageError, TSSError
from tss.core.logging import get_logger
from tss.core.settings import AppConfig
from tss.core.time import utc_now
from tss.db.repositories import ops

PHASE = "P1"

SUCCESS, PARTIAL, FAILED, SKIPPED = "SUCCESS", "PARTIAL", "FAILED", "SKIPPED"


@dataclass
class Deps:
    config: AppConfig
    session_factory: async_sessionmaker[AsyncSession]
    futures: MexcFuturesClient
    spot: MexcSpotClient


@dataclass
class AgentResult:
    status: str = SUCCESS
    rows_in: int | None = None
    rows_out: int | None = None
    selected_count: int | None = None
    meta: dict[str, Any] = field(default_factory=dict)
    event: str | None = None  # NOTIFY event type, e.g. "movers_updated"


@dataclass
class AgentOutcome:
    agent: str
    status: str
    error: TSSError | None = None
    result: AgentResult | None = None
    duration_s: float = 0.0


def is_db_unreachable(exc: BaseException) -> bool:
    if isinstance(exc, OperationalError | InterfaceError | ConnectionError):
        return True
    if isinstance(exc, DBAPIError) and exc.connection_invalidated:
        return True
    return isinstance(exc, OSError)


class BaseAgent:
    name: ClassVar[str]
    critical: ClassVar[bool] = False

    def __init__(self, deps: Deps) -> None:
        self.deps = deps
        self.log = get_logger(self.name)

    async def run(self, cycle_id: uuid.UUID, now: datetime) -> AgentResult:
        raise NotImplementedError

    def _wrap(self, exc: BaseException, operation: str) -> TSSError:
        if isinstance(exc, TSSError):
            return exc
        if is_db_unreachable(exc):
            return StorageError(
                self.name, PHASE, operation, f"database unreachable ({type(exc).__name__})"
            )
        return TSSError(self.name, PHASE, operation, f"unexpected {type(exc).__name__}: {exc}")

    async def execute(self, cycle_id: uuid.UUID, now: datetime) -> AgentOutcome:
        """Run once with full lifecycle. A DB failure while recording the run is re-raised as
        StorageError so the Control Agent can treat it as a critical halt.
        """
        started = time.monotonic()
        try:
            async with self.deps.session_factory() as session:
                run_id = await ops.start_run(session, self.name, cycle_id, now)
                await session.commit()
        except Exception as exc:
            raise self._wrap(exc, "start_run") from exc

        error: TSSError | None = None
        result: AgentResult | None = None
        try:
            result = await self.run(cycle_id, now)
            status = result.status
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            error = self._wrap(exc, getattr(exc, "operation", "run"))
            status = FAILED
            self.log.error(
                "agent run failed",
                component=error.component,
                phase=error.phase,
                op=error.operation,
                cycle_id=str(cycle_id),
                error=error.message,
            )

        duration = time.monotonic() - started
        try:
            async with self.deps.session_factory() as session:
                await ops.finish_run(
                    session,
                    run_id,
                    finished_at=utc_now(),
                    status=status,
                    rows_in=result.rows_in if result else None,
                    rows_out=result.rows_out if result else None,
                    selected_count=result.selected_count if result else None,
                    error_component=error.component if error else None,
                    error_phase=error.phase if error else None,
                    error_message=error.message if error else None,
                    meta=result.meta if result else None,
                )
                await ops.notify(
                    session,
                    "agent_status",
                    now,
                    {"agent": self.name, "status": status, "duration_s": round(duration, 2)},
                )
                if result and result.event and status in (SUCCESS, PARTIAL):
                    await ops.notify(session, result.event, now, result.meta)
                await session.commit()
        except Exception as exc:
            raise self._wrap(exc, "finish_run") from exc

        self.log.info(
            "agent run finished",
            component=self.name,
            phase=PHASE,
            op="run",
            cycle_id=str(cycle_id),
            status=status,
            rows_in=result.rows_in if result else None,
            rows_out=result.rows_out if result else None,
            duration_s=round(duration, 2),
        )
        return AgentOutcome(self.name, status, error, result, duration)
