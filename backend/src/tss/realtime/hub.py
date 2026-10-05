"""In-process event hub: fans NOTIFY events and ticks out to /ws clients (Arch §10)."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from typing import Any

QUEUE_SIZE = 256


class EventHub:
    """One queue per connected client. A slow client drops its oldest messages, never blocks."""

    def __init__(self) -> None:
        self._clients: set[asyncio.Queue[str]] = set()
        self._listeners: list[Callable[[dict[str, Any]], None]] = []
        self.last_ticks: dict[str, str] = {}

    def subscribe(self) -> asyncio.Queue[str]:
        queue: asyncio.Queue[str] = asyncio.Queue(maxsize=QUEUE_SIZE)
        for message in self.last_ticks.values():  # new clients start with current prices
            queue.put_nowait(message)
        self._clients.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[str]) -> None:
        self._clients.discard(queue)

    def add_listener(self, listener: Callable[[dict[str, Any]], None]) -> None:
        self._listeners.append(listener)

    @property
    def client_count(self) -> int:
        return len(self._clients)

    def publish(self, event: dict[str, Any]) -> None:
        message = json.dumps(event, default=str, separators=(",", ":"))
        if event.get("type") == "ticker":
            symbol = event.get("data", {}).get("symbol")
            if isinstance(symbol, str):
                self.last_ticks[symbol] = message
        for queue in tuple(self._clients):
            if queue.full():
                queue.get_nowait()
            queue.put_nowait(message)
        for listener in self._listeners:
            listener(event)

    def forget_ticks_except(self, symbols: set[str]) -> None:
        for symbol in set(self.last_ticks) - symbols:
            del self.last_ticks[symbol]
