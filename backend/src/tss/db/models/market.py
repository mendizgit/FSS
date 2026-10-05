"""Market data: market_snapshots, klines_15m, daily_opens (Arch §9)."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, Float, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from tss.db.base import Base, UTCDateTime


class MarketSnapshot(Base):
    __tablename__ = "market_snapshots"
    __table_args__ = (Index("ix_market_snapshots_ts", "ts"),)

    symbol: Mapped[str] = mapped_column(String(32), primary_key=True)
    ts: Mapped[datetime] = mapped_column(UTCDateTime, primary_key=True)
    last_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    fair_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    hold_vol: Mapped[float | None] = mapped_column(Float, nullable=True)
    oi_notional_usdt: Mapped[float | None] = mapped_column(Float, nullable=True)
    funding_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    fut_volume24: Mapped[float | None] = mapped_column(Float, nullable=True)
    fut_amount24: Mapped[float | None] = mapped_column(Float, nullable=True)
    liquid: Mapped[bool] = mapped_column(Boolean)
    spot_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    spot_quote_volume24: Mapped[float | None] = mapped_column(Float, nullable=True)


class Kline15m(Base):
    __tablename__ = "klines_15m"
    __table_args__ = (Index("ix_klines_15m_open_time", "open_time"),)

    symbol: Mapped[str] = mapped_column(String(32), primary_key=True)
    open_time: Mapped[datetime] = mapped_column(UTCDateTime, primary_key=True)
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[float | None] = mapped_column(Float, nullable=True)
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)


class DailyOpen(Base):
    __tablename__ = "daily_opens"

    symbol: Mapped[str] = mapped_column(String(32), primary_key=True)
    utc_date: Mapped[date] = mapped_column(Date, primary_key=True)
    open: Mapped[float] = mapped_column(Float)
