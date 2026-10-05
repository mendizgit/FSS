"""Pydantic response models (Arch §10). Timestamps are ISO-8601 UTC."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ApiError(BaseModel):
    code: str
    message: str
    component: str


class ErrorEnvelope(BaseModel):
    error: ApiError


class AgentRunOut(BaseModel):
    agent: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    rows_in: int | None
    rows_out: int | None
    selected_count: int | None
    error_component: str | None
    error_message: str | None
    meta: dict[str, Any] | None


class StatusOut(BaseModel):
    state: str
    reason: str | None
    state_updated_at: datetime | None
    runs: list[AgentRunOut]
    next_runs: dict[str, datetime | None]
    universe: dict[str, int]
    db_size_bytes: int
    telegram_configured: bool
    now: datetime


class UniverseSummaryOut(BaseModel):
    total: int
    active: int
    liquid: int
    denylisted: int
    zero_fee: int


class DiscoveryRow(BaseModel):
    symbol: str
    zero_fee: bool | None
    pinned: bool
    last_price: float | None
    price_change_15m_pct: float | None
    rvol_15m: float | None
    fut_amount24: float | None
    oi_notional_usdt: float | None
    funding_rate: float | None
    utc_day_change_pct: float | None
    pool_rank: int | None
    passed_gate2: bool
    selection_rank: int | None


class DiscoveryOut(BaseModel):
    cycle_id: uuid.UUID | None
    ts: datetime | None
    pool: list[DiscoveryRow]
    pinned: list[DiscoveryRow]


class ClassificationRow(BaseModel):
    symbol: str
    window: str
    ts: datetime
    pinned: bool
    last_price: float | None
    price_change_15m_pct: float | None
    price_change_pct: float | None
    oi_notional_usdt: float | None
    oi_change_pct: float | None
    fut_volume_change_pct: float | None
    spot_volume_change_pct: float | None
    funding_now: float | None
    funding_delta: float | None
    state: str
    flags: list[str]
    unreliable_reasons: list[str]


class ClassificationOut(BaseModel):
    window: str
    cycle_id: uuid.UUID | None
    ts: datetime | None
    rows: list[ClassificationRow]


class HistoryPoint(BaseModel):
    ts: datetime
    state: str
    price_change_pct: float | None
    oi_change_pct: float | None
    fut_volume_change_pct: float | None
    spot_volume_change_pct: float | None
    funding_now: float | None
    funding_delta: float | None
    flags: list[str]


class HistoryOut(BaseModel):
    symbol: str
    window: str
    hours: int
    points: list[HistoryPoint]


class MoverRowOut(BaseModel):
    rank: int
    symbol: str
    day_open: float | None
    last_price: float | None
    change_pct: float | None
    fut_amount24: float | None
    oi_notional_usdt: float | None
    funding_rate: float | None


class MoversOut(BaseModel):
    status: str  # OK | WAITING_DAY_OPEN | NO_DATA
    ts: datetime | None
    gainers: list[MoverRowOut]
    losers: list[MoverRowOut]


class NewsItemOut(BaseModel):
    id: int
    source: str
    title: str
    url: str
    published_at: datetime | None
    fetched_at: datetime
    symbols: list[str]


class NewsOut(BaseModel):
    symbol: str | None
    items: list[NewsItemOut]


class SignalRowOut(BaseModel):
    timeframe: str
    bar_close_time: datetime
    m_trend: str
    last_event: str
    bars_ago: int | None
    against_htf: bool | None
    htf_supertrend: str | None
    local_supertrend: str
    consolidated_trend: str
    long_score: int
    short_score: int
    long_grade: str
    short_grade: str
    rsi_divergence: str | None
    sr_letter: str | None
    zone_position: str | None
    price_vs_vwap: str | None
    computed_at: datetime


class SignalSymbolOut(BaseModel):
    symbol: str
    pinned: bool
    selection_rank: int | None
    rows: list[SignalRowOut]


class SignalsOut(BaseModel):
    updated_at: datetime | None
    symbols: list[SignalSymbolOut]
