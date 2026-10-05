"""F6 Live Ticker Gateway: MEXC futures WS -> throttled `ticker` events on the hub.

Subscribes `sub.ticker` for every symbol the dashboard shows, pings to keep the socket alive,
reconnects with backoff, re-subscribes on `cycle_complete` and `movers_updated`.
Ticks are never persisted.
"""

from __future__ import annotations

import asyncio
import json
import random
import time
from collections.abc import Awaitable, Callable
from typing import Any

import websockets

from tss.core.logging import get_logger
from tss.core.time import utc_now
from tss.realtime.hub import EventHub

COMPONENT = "ticker_gateway"
WS_URL = "wss://contract.mexc.com/edge"
PING_S = 15.0  # Arch §3.1: ping at most every 20 s
THROTTLE_S = 1.0  # at most 1 update per second per symbol
BACKOFF_S = (1.0, 2.0, 4.0, 8.0, 15.0, 30.0)
STABLE_S = 30.0  # a connection that lived this long resets the backoff

SymbolsProvider = Callable[[], Awaitable[set[str]]]


def tick_event(symbol: str, data: dict[str, Any]) -> dict[str, Any]:
    """Map a MEXC push.ticker payload to our event. Missing fields stay None (never invented)."""

    def num(key: str) -> float | None:
        value = data.get(key)
        return (
            float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None
        )

    return {
        "type": "ticker",
        "ts": utc_now().isoformat(),
        "data": {
            "symbol": symbol,
            "last_price": num("lastPrice"),
            "fair_price": num("fairPrice"),
        },
    }


class TickerGateway:
    def __init__(
        self,
        hub: EventHub,
        symbols: SymbolsProvider,
        url: str = WS_URL,
        *,
        ping_s: float = PING_S,
        throttle_s: float = THROTTLE_S,
        backoff_s: tuple[float, ...] = BACKOFF_S,
    ) -> None:
        self._hub = hub
        self._symbols = symbols
        self._url = url
        self._ping_s = ping_s
        self._throttle_s = throttle_s
        self._backoff = backoff_s
        self._resubscribe = asyncio.Event()
        self._last_sent: dict[str, float] = {}
        self._subscribed: set[str] = set()
        self.connected = False
        self.log = get_logger(COMPONENT)
        hub.add_listener(self._on_event)

    def _on_event(self, event: dict[str, Any]) -> None:
        if event.get("type") in ("cycle_complete", "movers_updated"):
            self._resubscribe.set()

    async def _sync_subscriptions(self, ws: Any) -> None:
        wanted = await self._symbols()
        for symbol in sorted(wanted - self._subscribed):
            await ws.send(json.dumps({"method": "sub.ticker", "param": {"symbol": symbol}}))
        for symbol in sorted(self._subscribed - wanted):
            await ws.send(json.dumps({"method": "unsub.ticker", "param": {"symbol": symbol}}))
        self._subscribed = wanted
        self._hub.forget_ticks_except(wanted)
        self.log.info(
            "subscriptions synced",
            component=COMPONENT,
            phase="P2",
            op="subscribe",
            symbols=len(wanted),
        )

    async def _pinger(self, ws: Any) -> None:
        while True:
            await asyncio.sleep(self._ping_s)
            await ws.send(json.dumps({"method": "ping"}))

    async def _resubscriber(self, ws: Any) -> None:
        while True:
            await self._resubscribe.wait()
            self._resubscribe.clear()
            await self._sync_subscriptions(ws)

    async def _session(self) -> None:
        async with websockets.connect(self._url, open_timeout=10, ping_interval=None) as ws:
            self.connected = True
            self._subscribed = set()
            self.log.info("connected", component=COMPONENT, phase="P2", op="connect")
            await self._sync_subscriptions(ws)
            helpers = [
                asyncio.create_task(self._pinger(ws)),
                asyncio.create_task(self._resubscriber(ws)),
            ]
            try:
                async for raw in ws:
                    self._handle(raw)
            finally:
                for task in helpers:
                    task.cancel()
                self.connected = False

    def _handle(self, raw: str | bytes) -> None:
        try:
            msg = json.loads(raw)
        except ValueError:
            return
        if msg.get("channel") != "push.ticker":
            return
        data = msg.get("data")
        symbol = msg.get("symbol") or (data or {}).get("symbol")
        if not isinstance(symbol, str) or not isinstance(data, dict):
            return
        now = time.monotonic()
        if now - self._last_sent.get(symbol, 0.0) < self._throttle_s:
            return
        self._last_sent[symbol] = now
        self._hub.publish(tick_event(symbol, data))

    async def run(self) -> None:
        attempt = 0
        while True:
            started = time.monotonic()
            try:
                await self._session()
                reason = "closed by server"
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                reason = type(exc).__name__
            if time.monotonic() - started >= STABLE_S:
                attempt = 0
            wait = self._backoff[min(attempt, len(self._backoff) - 1)] + random.random() * 0.5
            attempt += 1
            self.log.warning(
                "disconnected; reconnecting",
                component=COMPONENT,
                phase="P2",
                op="reconnect",
                reason=reason,
                wait_s=round(wait, 1),
            )
            await asyncio.sleep(wait)
