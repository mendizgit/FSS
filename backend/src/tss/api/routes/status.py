"""GET /api/status and /api/universe/summary."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from tss.api.deps import get_config, get_session
from tss.api.schemas.models import AgentRunOut, StatusOut, UniverseSummaryOut
from tss.control.schedule import (
    next_news,
    next_pipeline,
    next_retention,
    next_snapshot,
    next_universe,
)
from tss.core.settings import AppConfig
from tss.core.time import utc_now
from tss.db.repositories import contracts as contracts_repo
from tss.db.repositories import ops

router = APIRouter()
Session = Annotated[AsyncSession, Depends(get_session)]
Config = Annotated[AppConfig, Depends(get_config)]


@router.get("/status", response_model=StatusOut)
async def status(session: Session, cfg: Config) -> StatusOut:
    now = utc_now()
    state = await ops.get_system_state(session)
    runs = await ops.latest_runs(session)
    last_universe = next(
        (
            r.finished_at
            for r in runs
            if r.agent == "universe" and r.status in ("SUCCESS", "PARTIAL")
        ),
        None,
    )
    return StatusOut(
        state=state.state if state else "UNKNOWN",
        reason=state.reason if state else "worker has not reported yet",
        state_updated_at=state.updated_at if state else None,
        runs=[
            AgentRunOut(
                agent=r.agent,
                status=r.status,
                started_at=r.started_at,
                finished_at=r.finished_at,
                rows_in=r.rows_in,
                rows_out=r.rows_out,
                selected_count=r.selected_count,
                error_component=r.error_component,
                error_message=r.error_message,
                meta=r.meta,
            )
            for r in runs
        ],
        next_runs={
            "snapshot": next_snapshot(now),
            "pipeline": next_pipeline(now),
            "news": next_news(now),
            "retention": next_retention(now),
            "universe": next_universe(last_universe, cfg.thresholds.universe.refresh_hours, now),
        },
        universe=await contracts_repo.universe_counts(session),
        db_size_bytes=await ops.db_size_bytes(session),
        now=now,
    )


@router.get("/universe/summary", response_model=UniverseSummaryOut)
async def universe_summary(session: Session) -> UniverseSummaryOut:
    return UniverseSummaryOut(**await contracts_repo.universe_counts(session))
