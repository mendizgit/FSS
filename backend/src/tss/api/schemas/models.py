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


class PauseOut(BaseModel):
    paused: bool
    manual: bool  # a Pause / Start choice from the dashboard is in effect
    reason: str | None
    until: datetime | None


class StatusOut(BaseModel):
    state: str
    reason: str | None
    state_updated_at: datetime | None
    runs: list[AgentRunOut]
    next_runs: dict[str, datetime | None]
    universe: dict[str, int]
    db_size_bytes: int
    telegram_configured: bool
    telegram_paused: bool
    flags: dict[str, bool]
    pause: PauseOut
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
    day_open: float | None
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


class RecentEventOut(BaseModel):
    event: str  # BUY | SELL | BULL_T | BEAR_T
    bars_ago: int  # bars before this row's newest closed bar
    against_htf: bool | None


class SignalRowOut(BaseModel):
    timeframe: str
    bar_close_time: datetime
    m_trend: str
    last_event: str
    bars_ago: int | None
    against_htf: bool | None
    zone_position: str | None
    price_vs_vwap: str | None
    computed_at: datetime
    recent_events: list[RecentEventOut] = []  # BUY/SELL/BULL_T/BEAR_T, newest first


class SetupOut(BaseModel):
    bias: str  # "long" | "short"
    trigger_timeframe: str  # 15m
    score: int  # factors met out of 5
    factors: str  # e.g. "ST,1H,EMA"
    against_htf: bool | None  # vs the 4H SuperTrend; informational only
    minutes_ago: int  # minutes since the 15m bar closed


class SignalSymbolOut(BaseModel):
    symbol: str
    group: str  # "majors" | "momentum"
    pinned: bool
    selection_rank: int | None
    setup: SetupOut | None = None  # Long / Short setup (domain/setups.py)
    rows: list[SignalRowOut]


class SignalsOut(BaseModel):
    updated_at: datetime | None
    symbols: list[SignalSymbolOut]


class PaperTradeOut(BaseModel):
    id: int
    symbol: str
    side: str
    status: str
    opened_at: datetime
    entry_price: float
    stop_price: float
    target_price: float
    score: int | None
    factors: str | None
    against_htf: bool | None
    flip_events: str | None
    flip_confirms: bool
    mfe_pct: float | None
    mae_pct: float | None
    last_price: float | None  # open trades: latest snapshot price
    unrealized_usdt: float | None
    closed_at: datetime | None
    exit_price: float | None
    exit_reason: str | None
    pnl_usdt: float | None
    r_multiple: float | None


class PaperGroupOut(BaseModel):
    key: str
    trades: int
    wins: int
    pnl_usdt: float
    avg_r: float


class PaperSummaryOut(BaseModel):
    start_balance_usdt: float
    balance_usdt: float  # start + realized PnL
    realized_usdt: float
    unrealized_usdt: float
    margin_in_use_usdt: float
    open_trades: int
    closed_trades: int
    wins: int
    win_rate_pct: float | None
    avg_r: float | None
    profit_factor: float | None
    max_drawdown_usdt: float
    leverage: float
    margin_per_trade_usdt: float
    stop_pct: float
    reward_risk: float
    timeout_minutes: int


class PaperOut(BaseModel):
    summary: PaperSummaryOut
    open: list[PaperTradeOut]
    closed: list[PaperTradeOut]
    by_score: list[PaperGroupOut]
    by_flip_confirm: list[PaperGroupOut]
    by_htf: list[PaperGroupOut]
    by_exit: list[PaperGroupOut]
    by_side: list[PaperGroupOut]
