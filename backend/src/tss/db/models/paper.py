"""paper_trades: dummy-money trades opened on 15m entry alerts (analysis only, no real orders)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Float,
    Index,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from tss.db.base import Base, UTCDateTime


class PaperTrade(Base):
    __tablename__ = "paper_trades"
    __table_args__ = (
        UniqueConstraint("symbol", "side", "setup_detected_at", name="uq_paper_trade_setup"),
        CheckConstraint("side IN ('long', 'short')", name="side"),
        CheckConstraint("status IN ('open', 'closed')", name="status"),
        Index("ix_paper_trades_status", "status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32))
    side: Mapped[str] = mapped_column(String(5))
    status: Mapped[str] = mapped_column(String(6))
    setup_detected_at: Mapped[datetime] = mapped_column(UTCDateTime)
    opened_at: Mapped[datetime] = mapped_column(UTCDateTime)  # close of the 5m entry bar
    entry_price: Mapped[float] = mapped_column(Float)
    stop_price: Mapped[float] = mapped_column(Float)
    target_price: Mapped[float] = mapped_column(Float)
    margin_usdt: Mapped[float] = mapped_column(Float)
    notional_usdt: Mapped[float] = mapped_column(Float)
    # the gates at entry, kept for tuning
    score: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    factors: Mapped[str | None] = mapped_column(String(24), nullable=True)
    against_htf: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    flip_events: Mapped[str | None] = mapped_column(String(48), nullable=True)  # BUY:2,BULL_T:2
    flip_confirms: Mapped[bool] = mapped_column(Boolean, default=False)  # side-aligned flip seen
    # result
    mfe_pct: Mapped[float | None] = mapped_column(Float, nullable=True)  # best move for the side
    mae_pct: Mapped[float | None] = mapped_column(Float, nullable=True)  # worst move for the side
    closed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    exit_reason: Mapped[str | None] = mapped_column(String(12), nullable=True)
    fees_usdt: Mapped[float | None] = mapped_column(Float, nullable=True)
    pnl_usdt: Mapped[float | None] = mapped_column(Float, nullable=True)  # net of fees
    r_multiple: Mapped[float | None] = mapped_column(Float, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime)
