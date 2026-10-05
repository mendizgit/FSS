"""market_movers (Arch §9): top gainers/losers of the UTC day per snapshot ts."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, Float, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from tss.db.base import Base, UTCDateTime


class MarketMover(Base):
    __tablename__ = "market_movers"
    __table_args__ = (
        CheckConstraint("side IN ('GAINER', 'LOSER')", name="side"),
        Index("ix_market_movers_ts", "ts"),
    )

    ts: Mapped[datetime] = mapped_column(UTCDateTime, primary_key=True)
    side: Mapped[str] = mapped_column(String(8), primary_key=True)
    rank: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32))
    day_open: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    change_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    fut_amount24: Mapped[float | None] = mapped_column(Float, nullable=True)
    oi_notional_usdt: Mapped[float | None] = mapped_column(Float, nullable=True)
    funding_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
