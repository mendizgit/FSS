"""F6 acceptance: the ticker gateway against a local fake MEXC WebSocket server.

Checks subscription, ping keep-alive, throttling (<= 1 update/s/symbol), re-subscribe on
cycle_complete, automatic recovery after a network drop, and the /ws fan-out endpoint.
No network access, no secrets.

Run: uv run python scripts/simulate_ticker.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

import websockets
from fastapi import FastAPI
from starlette.testclient import TestClient

from tss.api import ws as ws_routes
from tss.realtime.hub import EventHub
from tss.realtime.ticker_gateway import TickerGateway

RESULTS: list[tuple[str, bool]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))


class FakeMexc:
    """Pushes 20 ticks/s per subscribed symbol; records client messages; can drop clients."""

    def __init__(self) -> None:
        self.received: list[dict[str, Any]] = []
        self.connections = 0
        self._sockets: list[Any] = []

    async def handler(self, ws: Any) -> None:
        self.connections += 1
        self._sockets.append(ws)
        subscribed: set[str] = set()

        async def pump() -> None:
            n = 0
            while True:
                await asyncio.sleep(0.05)
                n += 1
                for symbol in sorted(subscribed):
                    msg = {
                        "channel": "push.ticker",
                        "symbol": symbol,
                        "data": {"symbol": symbol, "lastPrice": 100.0 + n, "fairPrice": 100.0},
                    }
                    await ws.send(json.dumps(msg))

        task = asyncio.create_task(pump())
        try:
            async for raw in ws:
                msg = json.loads(raw)
                self.received.append(msg)
                if msg["method"] == "sub.ticker":
                    subscribed.add(msg["param"]["symbol"])
                elif msg["method"] == "unsub.ticker":
                    subscribed.discard(msg["param"]["symbol"])
                elif msg["method"] == "ping":
                    await ws.send(json.dumps({"channel": "pong", "data": 1}))
        finally:
            task.cancel()

    def methods(self, method: str) -> list[str | None]:
        return [m.get("param", {}).get("symbol") for m in self.received if m["method"] == method]

    async def drop_clients(self) -> None:
        for ws in self._sockets:
            await ws.close()
        self._sockets.clear()


async def gateway_checks() -> None:
    print("\nGateway against a fake MEXC WS")
    fake = FakeMexc()
    wanted = {"A_USDT", "B_USDT"}

    async def provider() -> set[str]:
        return set(wanted)

    hub = EventHub()
    events: list[dict[str, Any]] = []
    hub.add_listener(events.append)
    async with websockets.serve(fake.handler, "127.0.0.1", 0) as server:
        port = server.sockets[0].getsockname()[1]
        gateway = TickerGateway(
            hub, provider, f"ws://127.0.0.1:{port}", ping_s=0.5, backoff_s=(0.2, 0.4)
        )
        task = asyncio.create_task(gateway.run())
        try:
            await asyncio.sleep(3.2)
            subs = sorted(s for s in fake.methods("sub.ticker") if s)
            check("subscribes to every wanted symbol", subs == ["A_USDT", "B_USDT"], str(subs))
            check("gateway reports connected", gateway.connected)
            pings = len(fake.methods("ping"))
            check("sends keep-alive pings", pings >= 4, f"{pings} pings in ~3 s at 0.5 s")
            ticks = [e for e in events if e["type"] == "ticker"]
            per_symbol = {s: sum(1 for e in ticks if e["data"]["symbol"] == s) for s in wanted}
            check(
                "throttled to <= 1 update/s/symbol (server sent ~60 per symbol)",
                all(2 <= n <= 4 for n in per_symbol.values()),
                str(per_symbol),
            )
            check(
                "tick payload has symbol, last_price, fair_price; ts is UTC ISO",
                set(ticks[0]["data"]) == {"symbol", "last_price", "fair_price"}
                and ticks[0]["ts"].endswith("+00:00"),
            )
            check(
                "hub caches the latest tick per symbol for new clients",
                set(hub.last_ticks) == wanted,
            )

            wanted.clear()
            wanted.update({"B_USDT", "C_USDT"})
            hub.publish({"type": "cycle_complete", "ts": "t", "data": {}})
            await asyncio.sleep(0.5)
            check(
                "cycle_complete: subscribes the new symbol", "C_USDT" in fake.methods("sub.ticker")
            )
            check(
                "cycle_complete: unsubscribes the dropped symbol",
                fake.methods("unsub.ticker") == ["A_USDT"],
                str(fake.methods("unsub.ticker")),
            )
            check("dropped symbol's cached tick is forgotten", "A_USDT" not in hub.last_ticks)

            before = fake.connections
            n_events = len(events)
            await fake.drop_clients()  # simulated network drop
            await asyncio.sleep(2.0)
            check(
                "reconnects automatically after a drop",
                fake.connections == before + 1,
                f"connections {before} -> {fake.connections}",
            )
            resubs = sorted(s for s in fake.methods("sub.ticker") if s)
            check(
                "re-subscribes after reconnect",
                resubs.count("B_USDT") == 2 and resubs.count("C_USDT") == 2,
                str(resubs),
            )
            check("ticks flow again after recovery", len(events) > n_events + 2)
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


def ws_endpoint_checks() -> None:
    print("\n/ws endpoint")
    hub = EventHub()
    hub.publish({"type": "ticker", "ts": "t", "data": {"symbol": "A_USDT", "last_price": 1.0}})
    app = FastAPI()
    app.state.hub = hub
    app.include_router(ws_routes.router)
    with TestClient(app) as client, client.websocket_connect("/ws") as ws:
        first = json.loads(ws.receive_text())
        check(
            "new client immediately receives the cached tick",
            first["type"] == "ticker" and first["data"]["symbol"] == "A_USDT",
        )
        hub.publish({"type": "movers_updated", "ts": "t", "data": {"n": 1}})
        second = json.loads(ws.receive_text())
        check(
            "events are pushed live in {type, ts, data} shape",
            second == {"type": "movers_updated", "ts": "t", "data": {"n": 1}},
        )
        check("one subscriber registered", hub.client_count == 1)
    check("subscriber removed on disconnect", hub.client_count == 0)

    slow = hub.subscribe()
    for i in range(300):
        hub.publish({"type": "agent_status", "ts": "t", "data": {"i": i}})
    check("a slow client drops its oldest messages instead of blocking", slow.qsize() == 256)


async def main() -> int:
    await gateway_checks()
    ws_endpoint_checks()
    failed = [name for name, ok in RESULTS if not ok]
    print(f"\n{len(RESULTS)} checks, {len(failed)} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
