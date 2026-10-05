"""Phase 0 preflight: verify MEXC public endpoints/fields and news sources (Arch §3, §5).

Public GET requests and one WebSocket handshake only. No API keys, no private or trading
endpoints. Prints a table (item | status | detail); never prints secrets.

Run: uv run python scripts/preflight.py
"""

from __future__ import annotations

import asyncio
import itertools
import json
import statistics
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any

import httpx
import websockets

from tss.core.errors import DataSourceError
from tss.core.settings import AppConfig, load_config_or_exit

COMPONENT = "preflight"
FUT = "https://contract.mexc.com"
SPOT = "https://api.mexc.com"
WS_URL = "wss://contract.mexc.com/edge"
TIMEOUT = httpx.Timeout(15.0, connect=5.0)
PROBE = "BTC_USDT"

OK, FAIL, WARN, SKIP = "✓", "✗", "⚠", "-"


@dataclass
class Row:
    item: str
    status: str
    detail: str


ROWS: list[Row] = []


def add(item: str, status: str, detail: str) -> None:
    ROWS.append(Row(item, status, detail))


async def get_json(client: httpx.AsyncClient, url: str, op: str) -> Any:
    try:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise DataSourceError(COMPONENT, "P0", op, f"{type(exc).__name__}: {exc}") from exc


def missing_fields(sample: dict[str, Any], fields: list[str]) -> list[str]:
    return [f for f in fields if f not in sample or sample[f] is None]


async def check_futures_detail(client: httpx.AsyncClient) -> list[dict[str, Any]]:
    op = "contract/detail"
    try:
        body = await get_json(client, f"{FUT}/api/v1/contract/detail", op)
    except DataSourceError as exc:
        add(f"futures {op}", FAIL, exc.message)
        return []
    data = body.get("data") if isinstance(body, dict) else None
    if not isinstance(data, list) or not data:
        add(f"futures {op}", FAIL, f"unexpected shape: keys={list(body)[:6]}")
        return []
    add(f"futures {op} reachable", OK, f"{len(data)} contracts, success={body.get('success')}")
    required = ["symbol", "baseCoin", "quoteCoin", "settleCoin", "contractSize", "state"]
    miss = missing_fields(data[0], required)
    add(
        "detail required fields",
        FAIL if miss else OK,
        f"missing: {miss}" if miss else "all present",
    )
    states: dict[Any, int] = {}
    for c in data:
        states[c.get("state")] = states.get(c.get("state"), 0) + 1
    add(
        "detail state values",
        WARN,
        f"counts by raw state code: {dict(sorted(states.items(), key=str))}"
        " (meaning not documented in payload; confirm vs MEXC docs)",
    )
    fee_keys = [k for k in ("makerFeeRate", "takerFeeRate") if k in data[0]]
    add(
        "detail fee fields",
        OK if len(fee_keys) == 2 else WARN,
        f"present: {fee_keys}" if fee_keys else "not returned -> zero_fee stays NULL",
    )
    if len(fee_keys) == 2:
        zero = sum(1 for c in data if c.get("makerFeeRate") == 0 and c.get("takerFeeRate") == 0)
        add("detail zero-fee contracts", OK, f"{zero} with both fees == 0")
    usdt = [c for c in data if c.get("quoteCoin") == "USDT" and c.get("settleCoin") == "USDT"]
    by_state: dict[Any, int] = {}
    for c in usdt:
        by_state[c.get("state")] = by_state.get(c.get("state"), 0) + 1
    add("USDT perps (quote=settle=USDT)", OK, f"{len(usdt)} total; by state: {by_state}")
    return data


async def check_futures_ticker(
    client: httpx.AsyncClient, detail: list[dict[str, Any]], cfg: AppConfig
) -> None:
    op = "contract/ticker"
    try:
        body = await get_json(client, f"{FUT}/api/v1/contract/ticker", op)
    except DataSourceError as exc:
        add(f"futures {op}", FAIL, exc.message)
        return
    data = body.get("data") if isinstance(body, dict) else None
    if not isinstance(data, list) or not data:
        add(f"futures {op}", FAIL, "unexpected shape")
        return
    add(f"futures {op} reachable", OK, f"{len(data)} tickers (no symbol = all)")
    required = ["lastPrice", "fairPrice", "holdVol", "fundingRate", "amount24", "volume24"]
    miss = missing_fields(data[0], required)
    add(
        "ticker required fields",
        FAIL if miss else OK,
        f"missing: {miss}" if miss else "all present",
    )
    sizes = {c["symbol"]: float(c["contractSize"]) for c in detail if "contractSize" in c}
    liq = cfg.thresholds.liquidity
    liquid = 0
    for t in data:
        try:
            size = sizes[t["symbol"]]
            oi = float(t["holdVol"]) * size * float(t["fairPrice"])
            if float(t["amount24"]) >= liq.min_turnover_24h_usdt and oi >= liq.min_oi_notional_usdt:
                liquid += 1
        except (KeyError, TypeError, ValueError):
            continue
    add(
        "estimated liquid count",
        OK,
        f"{liquid} at turnover>={liq.min_turnover_24h_usdt:,.0f} "
        f"& OI>={liq.min_oi_notional_usdt:,.0f}"
        " (all contracts with a ticker, not only USDT)",
    )


async def check_futures_kline(client: httpx.AsyncClient) -> None:
    now = int(time.time())
    for interval in ("Min5", "Min15", "Min60", "Hour4"):
        start = now - 3600 * 24
        url = f"{FUT}/api/v1/contract/kline/{PROBE}?interval={interval}&start={start}&end={now}"
        try:
            body = await get_json(client, url, f"kline {interval}")
            n = len(body.get("data", {}).get("time", []))
            add(f"kline interval {interval}", OK if n else WARN, f"{n} bars for last 24h")
        except DataSourceError as exc:
            add(f"kline interval {interval}", FAIL, exc.message)
    url = f"{FUT}/api/v1/contract/kline/{PROBE}?interval=Min15&start={now - 86400 * 30}&end={now}"
    try:
        data = (await get_json(client, url, "kline max bars")).get("data", {})
        times = data.get("time", [])
        add(
            "kline max bars per call",
            WARN if times else FAIL,
            f"{len(times)} bars returned for a 30-day Min15 request (cap if < 2880)",
        )
        keys = [k for k in ("time", "open", "high", "low", "close", "vol", "amount") if k in data]
        add("kline fields", OK if "amount" in keys else WARN, f"keys: {keys}")
        if times:
            unit = "ms" if times[-1] > 10**11 else "s"
            add("kline time unit", OK, unit)
            step = statistics.median(b - a for a, b in itertools.pairwise(times))
            add("kline bar spacing", OK, f"median {step} {unit} (expected 900 s)")
            last_s = times[-1] / (1000 if unit == "ms" else 1)
            forming = last_s + 900 > now
            add(
                "forming bar included",
                WARN if forming else OK,
                "yes: last bar still open -> drop it (closed bars only)"
                if forming
                else "no: last bar is closed",
            )
    except DataSourceError as exc:
        add("kline max bars per call", FAIL, exc.message)


async def check_spot(client: httpx.AsyncClient) -> None:
    try:
        data = await get_json(client, f"{SPOT}/api/v3/ticker/24hr", "spot ticker")
        miss = missing_fields(data[0], ["symbol", "lastPrice", "quoteVolume"])
        add("spot ticker/24hr", FAIL if miss else OK, f"{len(data)} symbols; missing: {miss}")
    except (DataSourceError, IndexError, TypeError) as exc:
        add("spot ticker/24hr", FAIL, getattr(exc, "message", str(exc)))
    try:
        k = await get_json(
            client, f"{SPOT}/api/v3/klines?symbol=BTCUSDT&interval=15m&limit=3", "spot kline"
        )
        add("spot klines 15m", OK if k else WARN, f"{len(k)} rows, {len(k[0]) if k else 0} columns")
    except DataSourceError as exc:
        add("spot klines 15m", FAIL, exc.message)


async def check_ws() -> None:
    try:
        async with asyncio.timeout(20):
            async with websockets.connect(WS_URL, open_timeout=10) as ws:
                await ws.send(json.dumps({"method": "sub.ticker", "param": {"symbol": PROBE}}))
                channels: list[str] = []
                while True:
                    msg = json.loads(await ws.recv())
                    channels.append(str(msg.get("channel")))
                    if msg.get("channel") == "push.ticker":
                        fields = sorted(msg.get("data", {}).keys())
                        add(
                            "WS connect + sub.ticker", OK, f"push.ticker received; fields: {fields}"
                        )
                        break
                await ws.send(json.dumps({"method": "ping"}))
                reply = json.loads(await ws.recv())
                add("WS ping", OK, f"reply channel: {reply.get('channel')}")
    except Exception as exc:
        add("WS connect + sub.ticker", FAIL, f"{type(exc).__name__}: {exc}")


async def check_rss(client: httpx.AsyncClient, cfg: AppConfig) -> None:
    for src in cfg.news_sources.rss:
        if not src.enabled:
            add(f"RSS {src.name}", SKIP, "disabled")
            continue
        try:
            resp = await client.get(src.url, follow_redirects=True)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
            items = root.findall(".//item") or root.findall(".//{http://www.w3.org/2005/Atom}entry")
            add(
                f"RSS {src.name}",
                OK if items else WARN,
                f"HTTP {resp.status_code}, {len(items)} items",
            )
        except (httpx.HTTPError, ET.ParseError) as exc:
            add(f"RSS {src.name}", FAIL, f"{type(exc).__name__}: {exc}")
    cp_key = cfg.settings.cryptopanic_api_key
    key_present = cp_key is not None and bool(cp_key.get_secret_value().strip())
    add(
        "CryptoPanic",
        SKIP,
        "key present; not called in preflight (free-tier terms unverified)"
        if key_present
        else "no key set -> disabled (optional)",
    )


def print_table() -> None:
    w = max(len(r.item) for r in ROWS)
    print(f"\n{'ITEM'.ljust(w)}  ST  DETAIL\n{'-' * w}  --  ------")
    for r in ROWS:
        print(f"{r.item.ljust(w)}  {r.status}   {r.detail}")
    fails = sum(r.status == FAIL for r in ROWS)
    warns = sum(r.status == WARN for r in ROWS)
    print(f"\n{len(ROWS)} checks: {fails} failed, {warns} to review")


async def main() -> int:
    cfg = load_config_or_exit()
    async with httpx.AsyncClient(
        timeout=TIMEOUT, headers={"User-Agent": "tss-preflight/0"}
    ) as client:
        detail = await check_futures_detail(client)
        await check_futures_ticker(client, detail, cfg)
        await check_futures_kline(client)
        await check_spot(client)
        await check_rss(client, cfg)
    await check_ws()
    print_table()
    return 1 if any(r.status == FAIL for r in ROWS) else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
