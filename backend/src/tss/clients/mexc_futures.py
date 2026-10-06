"""MEXC futures public REST (no API key). Each method maps 1:1 to an endpoint (Arch §3.1)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError

from tss.clients.http import PHASE, HttpClient
from tss.clients.models import ContractDetail, FuturesTicker, Kline, from_epoch_s
from tss.core.errors import DataSourceError

COMPONENT = "mexc_futures"
BASE_URL = "https://contract.mexc.com"
HOST = "contract.mexc.com"


def validation_message(exc: PydanticValidationError) -> str:
    return "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()[:3])


def envelope_data(body: Any, path: str, operation: str) -> Any:
    """Unwrap MEXC's {success, code, data} envelope; anything else is a source error."""
    if not isinstance(body, dict) or body.get("success") is not True or "data" not in body:
        code = body.get("code") if isinstance(body, dict) else None
        raise DataSourceError(
            COMPONENT,
            PHASE,
            operation,
            f"unexpected response envelope from {path} (success/data missing, code={code})",
            {"endpoint": path},
        )
    return body["data"]


def parse_items[M: BaseModel](model: type[M], items: Any, path: str, operation: str) -> list[M]:
    if not isinstance(items, list):
        raise DataSourceError(
            COMPONENT,
            PHASE,
            operation,
            f"{path} data is not a list",
            {"endpoint": path},
        )
    out: list[M] = []
    for index, item in enumerate(items):
        try:
            out.append(model.model_validate(item))
        except PydanticValidationError as exc:
            raise DataSourceError(
                COMPONENT,
                PHASE,
                operation,
                f"{path} item {index} invalid: {validation_message(exc)}",
                {"endpoint": path, "index": index},
            ) from exc
    return out


class MexcFuturesClient:
    def __init__(self, http: HttpClient, base_url: str = BASE_URL) -> None:
        self._http = http
        self._base = base_url

    async def ping(self) -> None:
        """Reachability probe: one attempt, no retry. Raises DataSourceError when unreachable."""
        path = "/api/v1/contract/ping"
        body = await self._http.get_json(
            self._base + path, component=COMPONENT, operation="ping", attempts=1
        )
        envelope_data(body, path, "ping")

    async def contract_detail(self) -> list[ContractDetail]:
        path = "/api/v1/contract/detail"
        body = await self._http.get_json(
            self._base + path, component=COMPONENT, operation="contract_detail"
        )
        data = envelope_data(body, path, "contract_detail")
        return parse_items(ContractDetail, data, path, "contract_detail")

    async def tickers(self) -> list[FuturesTicker]:
        path = "/api/v1/contract/ticker"
        body = await self._http.get_json(
            self._base + path, component=COMPONENT, operation="tickers"
        )
        data = envelope_data(body, path, "tickers")
        return parse_items(FuturesTicker, data, path, "tickers")

    async def klines(
        self, symbol: str, interval: str, start: datetime, end: datetime
    ) -> list[Kline]:
        """Bars with open_time in [start, end]. The newest bar may still be forming."""
        path = f"/api/v1/contract/kline/{symbol}"
        op = "klines"
        body = await self._http.get_json(
            self._base + path,
            component=COMPONENT,
            operation=op,
            params={
                "interval": interval,
                "start": int(start.timestamp()),
                "end": int(end.timestamp()),
            },
        )
        data = envelope_data(body, path, op)
        if not isinstance(data, dict):
            raise DataSourceError(
                COMPONENT, PHASE, op, f"{path} data is not an object", {"endpoint": path}
            )
        columns = ("time", "open", "high", "low", "close", "vol", "amount")
        for col in columns:
            if not isinstance(data.get(col), list):
                raise DataSourceError(
                    COMPONENT, PHASE, op, f"{path} missing column '{col}'", {"endpoint": path}
                )
        n = len(data["time"])
        if any(len(data[col]) != n for col in columns):
            raise DataSourceError(
                COMPONENT, PHASE, op, f"{path} columns have different lengths", {"endpoint": path}
            )
        try:
            return [
                Kline(
                    open_time=from_epoch_s(data["time"][i]),
                    open=data["open"][i],
                    high=data["high"][i],
                    low=data["low"][i],
                    close=data["close"][i],
                    volume=data["vol"][i],
                    amount=data["amount"][i],
                )
                for i in range(n)
            ]
        except (PydanticValidationError, TypeError, ValueError) as exc:
            raise DataSourceError(
                COMPONENT, PHASE, op, f"{path} has a malformed bar", {"endpoint": path}
            ) from exc
