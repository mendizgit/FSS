"""MEXC spot public REST (no API key). Optional per symbol (Arch §3.2)."""

from __future__ import annotations

from typing import Any

from tss.clients.http import PHASE, HttpClient
from tss.clients.mexc_futures import parse_items
from tss.clients.models import SpotKline, SpotTicker, from_epoch_s
from tss.core.errors import DataSourceError

COMPONENT = "mexc_spot"
BASE_URL = "https://api.mexc.com"
HOST = "api.mexc.com"


class MexcSpotClient:
    def __init__(self, http: HttpClient, base_url: str = BASE_URL) -> None:
        self._http = http
        self._base = base_url

    async def tickers_24h(self) -> list[SpotTicker]:
        path = "/api/v3/ticker/24hr"
        body = await self._http.get_json(
            self._base + path, component=COMPONENT, operation="tickers_24h"
        )
        return parse_items(SpotTicker, body, path, "tickers_24h")

    async def klines_15m(self, spot_symbol: str, limit: int) -> list[SpotKline]:
        """Rows: [openTime ms, o, h, l, c, vol, closeTime ms, quoteVol]. Newest may be forming."""
        path = "/api/v3/klines"
        op = "klines_15m"
        body: Any = await self._http.get_json(
            self._base + path,
            component=COMPONENT,
            operation=op,
            params={"symbol": spot_symbol, "interval": "15m", "limit": limit},
        )
        if not isinstance(body, list):
            raise DataSourceError(COMPONENT, PHASE, op, f"{path} is not a list", {"endpoint": path})
        out: list[SpotKline] = []
        for index, row in enumerate(body):
            try:
                quote = row[7]
                out.append(
                    SpotKline(
                        open_time=from_epoch_s(int(row[0]) / 1000),
                        close=float(row[4]),
                        quote_volume=None if quote in (None, "") else float(quote),
                    )
                )
            except (IndexError, TypeError, ValueError) as exc:
                raise DataSourceError(
                    COMPONENT, PHASE, op, f"{path} row {index} malformed", {"endpoint": path}
                ) from exc
        return out
