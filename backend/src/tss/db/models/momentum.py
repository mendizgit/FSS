"""momentum_rankings (Arch §9). cycle_id is a UUID shared by one 15-min pipeline run."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Float, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from tss.db.base import Base, UTCDateTime


class MomentumRanking(Base):
    __tablename__ = "momentum_rankings"

    cycle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), primary_key=True)
    ts: Mapped[datetime] = mapped_column(UTCDateTime)
    pool_rank: Mapped[int] = mapped_column(Integer)
    price_change_15m_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    rvol_15m: Mapped[float | None] = mapped_column(Float, nullable=True)
    passed_gate2: Mapped[bool] = mapped_column(Boolean)
    selection_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pinned: Mapped[bool] = mapped_column(Boolean)
