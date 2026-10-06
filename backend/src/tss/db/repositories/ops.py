"""agent_runs, system_state, NOTIFY and status helpers (Arch §8-§9)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import delete, func, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from tss.db.models import AgentRun, ControlFlag, NewsItem, SystemState

CHANNEL = "tss_events"


async def start_run(
    session: AsyncSession, agent: str, cycle_id: uuid.UUID | None, started_at: datetime
) -> int:
    run = AgentRun(agent=agent, cycle_id=cycle_id, started_at=started_at, status="RUNNING")
    session.add(run)
    await session.flush()
    return run.id


async def finish_run(
    session: AsyncSession,
    run_id: int,
    *,
    finished_at: datetime,
    status: str,
    rows_in: int | None = None,
    rows_out: int | None = None,
    selected_count: int | None = None,
    error_component: str | None = None,
    error_phase: str | None = None,
    error_message: str | None = None,
    meta: dict[str, Any] | None = None,
) -> None:
    await session.execute(
        update(AgentRun)
        .where(AgentRun.id == run_id)
        .values(
            finished_at=finished_at,
            status=status,
            rows_in=rows_in,
            rows_out=rows_out,
            selected_count=selected_count,
            error_component=error_component,
            error_phase=error_phase,
            error_message=error_message,
            meta=meta,
        )
    )


async def latest_runs(session: AsyncSession) -> list[AgentRun]:
    ranked = (
        select(
            AgentRun.id,
            func.row_number()
            .over(partition_by=AgentRun.agent, order_by=AgentRun.started_at.desc())
            .label("rn"),
        )
    ).subquery()
    result = await session.execute(
        select(AgentRun)
        .join(ranked, ranked.c.id == AgentRun.id)
        .where(ranked.c.rn == 1)
        .order_by(AgentRun.agent)
    )
    return list(result.scalars())


async def get_system_state(session: AsyncSession) -> SystemState | None:
    return (
        await session.execute(select(SystemState).where(SystemState.id == 1))
    ).scalar_one_or_none()


async def set_system_state(
    session: AsyncSession, state: str, reason: str | None, now: datetime
) -> bool:
    """Upsert the singleton row. Returns True if state or reason changed."""
    current = await get_system_state(session)
    changed = current is None or current.state != state or current.reason != reason
    if changed:
        stmt = insert(SystemState).values(id=1, state=state, reason=reason, updated_at=now)
        await session.execute(
            stmt.on_conflict_do_update(
                index_elements=["id"],
                set_={"state": state, "reason": reason, "updated_at": now},
            )
        )
    return changed


MAX_NOTIFY_BYTES = 7000  # Postgres rejects NOTIFY payloads of about 8000 bytes or more


async def notify(
    session: AsyncSession, event_type: str, ts: datetime, data: dict[str, Any]
) -> None:
    payload = json.dumps({"type": event_type, "ts": ts.isoformat(), "data": data}, default=str)
    if len(payload.encode()) > MAX_NOTIFY_BYTES:  # keep the event, drop the oversized detail
        payload = json.dumps(
            {"type": event_type, "ts": ts.isoformat(), "data": {"truncated": True}}
        )
    await session.execute(text("SELECT pg_notify(:ch, :p)"), {"ch": CHANNEL, "p": payload})


async def db_size_bytes(session: AsyncSession) -> int:
    return int(
        (await session.execute(text("SELECT pg_database_size(current_database())"))).scalar_one()
    )


async def ping(session: AsyncSession) -> None:
    await session.execute(text("SELECT 1"))


async def purge_ops(session: AsyncSession, cutoff: datetime) -> dict[str, int]:
    runs = await session.execute(delete(AgentRun).where(AgentRun.started_at < cutoff))
    news = await session.execute(delete(NewsItem).where(NewsItem.fetched_at < cutoff))
    return {
        "agent_runs": int(getattr(runs, "rowcount", 0) or 0),
        "news_items": int(getattr(news, "rowcount", 0) or 0),
    }


async def get_flags(session: AsyncSession) -> dict[str, bool]:
    rows = (await session.execute(select(ControlFlag))).scalars().all()
    return {r.key: r.enabled for r in rows}


async def get_flag_row(session: AsyncSession, key: str) -> ControlFlag | None:
    return (
        await session.execute(select(ControlFlag).where(ControlFlag.key == key))
    ).scalar_one_or_none()


async def set_flag(session: AsyncSession, key: str, enabled: bool, now: datetime) -> None:
    stmt = insert(ControlFlag).values(key=key, enabled=enabled, updated_at=now)
    await session.execute(
        stmt.on_conflict_do_update(
            index_elements=["key"], set_={"enabled": enabled, "updated_at": now}
        )
    )
