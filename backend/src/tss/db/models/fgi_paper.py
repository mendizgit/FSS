"""fgi_paper_trades: dummy-money trades of the FGI Pro strategy (analysis only, no real orders)."""

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


class FgiPaperTrade(Base):
    __tablename__ = "fgi_paper_trades"
    __table_args__ = (
        UniqueConstraint("symbol", "side", "signal_at", name="uq_fgi_paper_trade_signal"),
        CheckConstraint("side IN ('long', 'short')", name="side"),
        CheckConstraint("status IN ('open', 'closed')", name="status"),
        Index("ix_fgi_paper_trades_status", "status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32))
    side: Mapped[str] = mapped_column(String(5))
    status: Mapped[str] = mapped_column(String(6))
    signal_at: Mapped[datetime] = mapped_column(UTCDateTime)  # close of the 15m signal bar
    opened_at: Mapped[datetime] = mapped_column(UTCDateTime)  # close of the 5m entry bar
    entry_price: Mapped[float] = mapped_column(Float)
    stop_price: Mapped[float] = mapped_column(Float)  # current (moves to break-even after TP1)
    stop0_price: Mapped[float] = mapped_column(Float)  # initial
    tp1_price: Mapped[float] = mapped_column(Float)
    tp2_price: Mapped[float] = mapped_column(Float)
    atr: Mapped[float] = mapped_column(Float)
    qty: Mapped[float] = mapped_column(Float)
    margin_usdt: Mapped[float] = mapped_column(Float)
    notional_usdt: Mapped[float] = mapped_column(Float)
    score: Mapped[int] = mapped_column(SmallInteger)  # factors met out of 6
    adx: Mapped[float] = mapped_column(Float)
    # running state of the position
    remaining_frac: Mapped[float] = mapped_column(Float)
    tp1_done: Mapped[bool] = mapped_column(Boolean, default=False)
    be: Mapped[bool] = mapped_column(Boolean, default=False)
    flip_pending: Mapped[bool] = mapped_column(Boolean, default=False)
    gross_usdt: Mapped[float] = mapped_column(Float, default=0.0)  # closed legs, before fees
    fees_usdt: Mapped[float] = mapped_column(Float, default=0.0)
    scanned_to: Mapped[datetime] = mapped_column(UTCDateTime)  # close of the last 5m bar applied
    mfe_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    mae_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    # result
    closed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    exit_reason: Mapped[str | None] = mapped_column(String(8), nullable=True)
    pnl_usdt: Mapped[float | None] = mapped_column(Float, nullable=True)  # net of fees
    r_multiple: Mapped[float | None] = mapped_column(Float, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime)
