"""signals and signal_events (Arch §9, Phase 4)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, Index, Integer, SmallInteger, String
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
    # entry score (15m entry signal; filled on every timeframe, NULL on rows from before v3)
    htf_dir: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True
    )  # 4H ST: -1 bull, 1 bear
    long_score: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    short_score: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    long_factors: Mapped[str | None] = mapped_column(String(24), nullable=True)
    short_factors: Mapped[str | None] = mapped_column(String(24), nullable=True)
    entry_long: Mapped[bool | None] = mapped_column(Boolean, nullable=True)  # SAR ok and score ok
    entry_short: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    stoch_dir: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)  # 5m rows only


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


class SignalSetup(Base):
    """Latest 15m entry signal (Long / Short) per symbol, for Telegram alerts (domain/setups.py).

    Alert on the rising edge only (notified_at NULL -> claimed -> sent), at most once per symbol and
    side per cooldown (last_long_alert_at / last_short_alert_at). trigger_event, htf_event and
    htf_bars_ago belong to the replaced event-based rule and stay NULL for entry signals.
    """

    __tablename__ = "signal_setups"
    __table_args__ = (CheckConstraint("bias IN ('long', 'short')", name="bias"),)

    symbol: Mapped[str] = mapped_column(String(32), primary_key=True)
    bias: Mapped[str] = mapped_column(String(5))
    active: Mapped[bool] = mapped_column(Boolean)
    trigger_timeframe: Mapped[str] = mapped_column(String(4))
    trigger_event: Mapped[str | None] = mapped_column(String(8), nullable=True)  # legacy
    trigger_bar_close_time: Mapped[datetime] = mapped_column(UTCDateTime)
    against_htf: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    htf_event: Mapped[str | None] = mapped_column(String(8), nullable=True)  # legacy
    htf_bars_ago: Mapped[int | None] = mapped_column(Integer, nullable=True)  # legacy
    score: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    factors: Mapped[str | None] = mapped_column(String(24), nullable=True)
    last_long_alert_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    last_short_alert_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    detected_at: Mapped[datetime] = mapped_column(UTCDateTime)
    notified_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime)
