"""Contract catalogue (Arch §9 `contracts`). Identity is the MEXC futures symbol BASE_USDT."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Float, Integer, String, false
from sqlalchemy.orm import Mapped, mapped_column

from tss.db.base import Base, UTCDateTime


class Contract(Base):
    __tablename__ = "contracts"

    symbol: Mapped[str] = mapped_column(String(32), primary_key=True)
    base_coin: Mapped[str] = mapped_column(String(32))
    quote_coin: Mapped[str] = mapped_column(String(16))
    settle_coin: Mapped[str] = mapped_column(String(16))
    contract_size: Mapped[float] = mapped_column(Float)
    state: Mapped[int] = mapped_column(
        Integer
    )  # raw MEXC state code; meaning confirmed in preflight
    maker_fee_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    taker_fee_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    zero_fee: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    denylisted: Mapped[bool] = mapped_column(Boolean, server_default=false())
    pinned: Mapped[bool] = mapped_column(Boolean, server_default=false())
    spot_symbol: Mapped[str | None] = mapped_column(String(32), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime)
