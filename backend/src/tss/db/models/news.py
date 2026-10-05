"""news_items (Arch §9)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from tss.db.base import Base, UTCDateTime


class NewsItem(Base):
    __tablename__ = "news_items"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text, unique=True)
    published_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    symbols: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    fetched_at: Mapped[datetime] = mapped_column(UTCDateTime)
