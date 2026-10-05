"""classifications (Arch §9). One row per (cycle, symbol, window)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, Float, Index, String
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from tss.db.base import Base, UTCDateTime


class Classification(Base):
    __tablename__ = "classifications"
    __table_args__ = (
        CheckConstraint("\"window\" IN ('1h', '4h')", name="window"),
        Index("ix_classifications_ts_symbol", "ts", "symbol"),
    )

    cycle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), primary_key=True)
    window: Mapped[str] = mapped_column(String(4), primary_key=True)
    ts: Mapped[datetime] = mapped_column(UTCDateTime)
    price_change_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    oi_change_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    fut_volume_change_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    spot_volume_change_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    funding_now: Mapped[float | None] = mapped_column(Float, nullable=True)
    funding_delta: Mapped[float | None] = mapped_column(Float, nullable=True)
    state: Mapped[str] = mapped_column(String(64))
    flags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    unreliable_reasons: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
