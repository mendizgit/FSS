"""Operational tables: agent_runs, system_state (Arch §9)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, CheckConstraint, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from tss.db.base import Base, UTCDateTime

AGENT_RUN_STATUSES = ("RUNNING", "SUCCESS", "PARTIAL", "FAILED", "SKIPPED", "HALTED")
SYSTEM_STATES = ("RUNNING", "DEGRADED", "HALTED", "WARMING_UP")


def _in_list(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class AgentRun(Base):
    __tablename__ = "agent_runs"
    __table_args__ = (
        CheckConstraint(_in_list("status", AGENT_RUN_STATUSES), name="status"),
        Index("ix_agent_runs_agent_started_at", "agent", text("started_at DESC")),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    agent: Mapped[str] = mapped_column(String(64))
    cycle_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(16))
    rows_in: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rows_out: Mapped[int | None] = mapped_column(Integer, nullable=True)
    selected_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_component: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_phase: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)


class SystemState(Base):
    __tablename__ = "system_state"
    __table_args__ = (
        CheckConstraint("id = 1", name="singleton"),
        CheckConstraint(_in_list("state", SYSTEM_STATES), name="state"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    state: Mapped[str] = mapped_column(String(16))
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime)
