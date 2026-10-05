"""Typed payload models for MEXC public endpoints.

Rules: parse numbers explicitly; empty/missing optional values become None, never 0; a missing
or malformed identity/required field raises (the client wraps it in DataSourceError).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise ValueError("boolean is not a number")
    return float(value)


def _to_float_required(value: Any) -> float:
    number = _to_float(value)
    if number is None:
        raise ValueError("required number is missing")
    return number


OptNum = Annotated[float | None, BeforeValidator(_to_float)]
ReqNum = Annotated[float, BeforeValidator(_to_float_required)]


class _Payload(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)


class ContractDetail(_Payload):
    symbol: str
    baseCoin: str
    quoteCoin: str
    settleCoin: str
    contractSize: ReqNum
    state: int
    makerFeeRate: OptNum = None
    takerFeeRate: OptNum = None


class FuturesTicker(_Payload):
    symbol: str
    lastPrice: OptNum = None
    fairPrice: OptNum = None
    holdVol: OptNum = None
    fundingRate: OptNum = None
    volume24: OptNum = None
    amount24: OptNum = None


class SpotTicker(_Payload):
    symbol: str
    lastPrice: OptNum = None
    quoteVolume: OptNum = None


class Kline(BaseModel):
    """One 15m (or other) bar. `open_time` is UTC. `amount` is turnover in USDT."""

    model_config = ConfigDict(frozen=True)

    open_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float | None
    amount: float | None


class SpotKline(BaseModel):
    model_config = ConfigDict(frozen=True)

    open_time: datetime
    close: float
    quote_volume: float | None


def from_epoch_s(value: int | float) -> datetime:
    return datetime.fromtimestamp(value, tz=UTC)
