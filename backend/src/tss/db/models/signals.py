"""signals and signal_events (Arch §9, Phase 4)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from tss.db.base import Base, UTCDateTime

TIMEFRAMES = ("5m", "15m", "1h")


class Signal(Base):
    """One row per (symbol, timeframe, closed bar). The newest row per pair is the live state."""

    __tablename__ = "signals"
    __table_args__ = (
        CheckConstraint("timeframe IN ('5m', '15m', '1h')", name="timeframe"),
        Index("ix_signals_computed_at", "computed_at"),
    )

    symbol: Mapped[str] = mapped_column(String(32), primary_key=True)
    timeframe: Mapped[str] = mapped_column(String(4), primary_key=True)
    bar_close_time: Mapped[datetime] = mapped_column(UTCDateTime, primary_key=True)
    m_trend: Mapped[str] = mapped_column(String(8))
    last_event: Mapped[str] = mapped_column(String(8))
    bars_ago: Mapped[int | None] = mapped_column(Integer, nullable=True)
    against_htf: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    zone_position: Mapped[str | None] = mapped_column(String(16), nullable=True)
    price_vs_vwap: Mapped[str | None] = mapped_column(String(8), nullable=True)
    computed_at: Mapped[datetime] = mapped_column(UTCDateTime)


class SignalEvent(Base):
    """An event on a closed bar. notified_at is set by the Telegram phase (P5)."""

    __tablename__ = "signal_events"
    __table_args__ = (Index("ix_signal_events_bar_close_time", "bar_close_time"),)

    symbol: Mapped[str] = mapped_column(String(32), primary_key=True)
    timeframe: Mapped[str] = mapped_column(String(4), primary_key=True)
    bar_close_time: Mapped[datetime] = mapped_column(UTCDateTime, primary_key=True)
    event: Mapped[str] = mapped_column(String(8), primary_key=True)
    against_htf: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    notified_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
