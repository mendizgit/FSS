"""F8 acceptance: the News agent against mocked RSS feeds on a throwaway database.

Covers URL dedupe, symbol tagging, rejected schemes, old / future dates, one failing source
(PARTIAL, named in the run meta), all sources failing (FAILED, degraded not halted),
NOTIFY news_new, /api/news (order, limit, symbol filter, validation) and retention.
No network access, no secrets.

Run: uv run python scripts/simulate_news.py
"""

from __future__ import annotations

import asyncio
import json
import sys
import uuid
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from typing import Any

import asyncpg  # type: ignore[import-untyped]
import httpx
from sqlalchemy import func, select

import simulate_failures as sf
from tss.agents.news import NewsAgent
from tss.clients.http import HttpClient
from tss.clients.rss import RssClient
from tss.core.settings import (
    AppConfig,
    CryptoPanicCfg,
    NewsSources,
    RssSource,
    load_config_or_exit,
)
from tss.db.models import NewsItem
from tss.db.repositories import ops
from tss.realtime.notify import asyncpg_dsn

check = sf.check


def rss(items: list[tuple[str, str, datetime | None]]) -> str:
    body = ""
    for title, link, published in items:
        date = f"<pubDate>{format_datetime(published)}</pubDate>" if published else ""
        body += f"<item><title>{title}</title><link>{link}</link>{date}</item>"
    return (
        f'<?xml version="1.0"?><rss version="2.0"><channel><title>t</title>{body}</channel></rss>'
    )


NOW = datetime.now(UTC).replace(microsecond=0)
FEED_A = rss(
    [
        (
            "BTC jumps as ETH follows",
            "https://a.test/btc?utm_source=rss&id=1",
            NOW - timedelta(minutes=10),
        ),
        ("AAA and THE market", "https://a.test/aaa", NOW - timedelta(minutes=30)),
        ("Dropped scheme", "javascript:alert(1)", NOW),
        ("", "https://a.test/no-title", NOW),
        ("Ancient story about BTC", "https://a.test/old", NOW - timedelta(days=10)),
        ("Future dated ETH story", "https://a.test/future", NOW + timedelta(days=2)),
        ("No date story", "https://a.test/nodate", None),
    ]
)
FEED_B = rss(
    [
        ("BTC jumps as ETH follows (copy)", "https://A.test/btc?id=1&fbclid=zzz#top", NOW),
        ("Second source exclusive", "https://b.test/exclusive", NOW - timedelta(minutes=5)),
    ]
)


def transport(routes: dict[str, httpx.Response | Exception]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        result = routes[request.url.host]
        if isinstance(result, Exception):
            raise result
        return result

    return httpx.MockTransport(handler)


def news_config(cfg: AppConfig, names: list[str], stoplist: list[str]) -> AppConfig:
    sources = NewsSources(
        rss=[RssSource(name=n, url=f"https://{n.lower()}.test/feed", enabled=True) for n in names],
        cryptopanic=CryptoPanicCfg(enabled=False),
        symbol_stoplist=stoplist,
    )
    return AppConfig(
        settings=cfg.settings,
        thresholds=cfg.thresholds,
        denylist=cfg.denylist,
        news_sources=sources,
    )


async def counts(c: Any) -> tuple[int, list[Any]]:
    async with c.deps.session_factory() as s:
        rows = list((await s.execute(select(NewsItem).order_by(NewsItem.id))).scalars())
    return len(rows), rows


async def scenario_mixed_sources(cfg: AppConfig, dsn: str) -> None:
    print("\n1. Mixed sources: dedupe, tagging, rejects, one source failing")
    ncfg = news_config(cfg, ["A", "B", "C", "D"], stoplist=["AAA"])
    c = sf.make_controller(ncfg, sf.FakeFutures(), sf.FakeSpot())
    await c.universe_job()  # contracts BTC / ETH / AAA
    http = HttpClient(
        {},
        client=httpx.AsyncClient(
            transport=transport(
                {
                    "a.test": httpx.Response(200, text=FEED_A),
                    "b.test": httpx.Response(200, text=FEED_B),
                    "c.test": httpx.Response(500),
                    "d.test": httpx.Response(200, text="<html><body>not a feed</body></html>"),
                }
            )
        ),
        sleep=lambda s: asyncio.sleep(0),
    )
    # route by source name -> host: sources are https://<name>.test/feed
    agent = NewsAgent(c.deps, RssClient(http))

    conn = await asyncpg.connect(dsn)
    events: list[dict[str, Any]] = []
    await conn.add_listener("tss_events", lambda *a: events.append(json.loads(a[3])))
    outcome = await agent.execute(uuid.uuid4(), NOW)
    await asyncio.sleep(0.3)
    meta = (outcome.result.meta if outcome.result else {}) or {}

    check("one failing source gives PARTIAL", outcome.status == "PARTIAL", outcome.status)
    check(
        "failed sources are named in the run meta",
        meta.get("failed") == ["C", "D"],
        str(meta.get("failed")),
    )
    check(
        "source C error is HTTP, D error says not a feed",
        "HTTP 500" in meta["sources"]["C"]["error"]
        and "valid RSS" in meta["sources"]["D"]["error"],
        str({k: v.get("error") for k, v in meta["sources"].items() if v["status"] == "failed"}),
    )
    n, rows = await counts(c)
    urls = sorted(r.url for r in rows)
    check("stored: btc (deduped), aaa, future, nodate, exclusive = 5 items", n == 5, f"{n}: {urls}")
    check(
        "tracking params and fragment are stripped; host lower-cased",
        "https://a.test/btc?id=1" in urls,
        str(urls),
    )
    check(
        "javascript: URL, empty title and 10-day-old item are rejected",
        not any("javascript" in u or "no-title" in u or "/old" in u for u in urls)
        and meta["skipped"] == {"bad_url": 1, "no_title": 1, "too_old": 1},
        str(meta["skipped"]),
    )
    by_url = {r.url: r for r in rows}
    check(
        "duplicate across sources: first source wins",
        by_url["https://a.test/btc?id=1"].source == "A",
    )
    check(
        "BTC and ETH are tagged (contract symbols)",
        by_url["https://a.test/btc?id=1"].symbols == ["BTC_USDT", "ETH_USDT"],
        str(by_url["https://a.test/btc?id=1"].symbols),
    )
    check(
        "stoplisted base (AAA) and non-coin word (THE) are not tagged",
        by_url["https://a.test/aaa"].symbols == [],
    )
    check(
        "future-dated item has no publication time (not invented)",
        by_url["https://a.test/future"].published_at is None,
    )
    check(
        "item without a date has no publication time",
        by_url["https://a.test/nodate"].published_at is None,
    )
    check("only title/url/source/times stored", all(r.title and r.fetched_at == NOW for r in rows))
    news_events = [e for e in events if e["type"] == "news_new"]
    check(
        "NOTIFY news_new sent once with the new count",
        len(news_events) == 1 and news_events[0]["data"]["new"] == 5,
        str(news_events),
    )

    second = await agent.execute(uuid.uuid4(), NOW + timedelta(minutes=15))
    await asyncio.sleep(0.3)
    n2, _ = await counts(c)
    check(
        "re-run is idempotent: no new rows, no news_new event",
        n2 == 5
        and (second.result.rows_out if second.result else None) == 0
        and len([e for e in events if e["type"] == "news_new"]) == 1,
    )
    await conn.close()

    # --- API ---
    code, body = await sf.api_get(ncfg, "/api/news")
    items = body["items"]
    check(
        "/api/news responds with all stored items",
        code == 200 and len(items) == 5,
        f"{code} {len(items)}",
    )
    times = [i["published_at"] or i["fetched_at"] for i in items]
    check("order is non-increasing by time", times == sorted(times, reverse=True), str(times))
    _, limited = await sf.api_get(ncfg, "/api/news?limit=2")
    check("limit is honoured", len(limited["items"]) == 2)
    _, base = await sf.api_get(ncfg, "/api/news?symbol=BTC")
    _, full = await sf.api_get(ncfg, "/api/news?symbol=BTC_USDT")
    check(
        "symbol filter accepts base or contract symbol",
        len(base["items"]) == 1 == len(full["items"]) and base["symbol"] == "BTC_USDT",
    )
    code, err = await sf.api_get(ncfg, "/api/news?symbol=btc%27%3B--")
    check(
        "invalid symbol -> 422 error envelope",
        code == 422 and err["error"]["code"] == "invalid_request",
        str(err),
    )
    code, err = await sf.api_get(ncfg, "/api/news?limit=9999")
    check("limit above 200 -> 422", code == 422)
    st = await sf.api_status(ncfg)
    news_run = next(r for r in st["runs"] if r["agent"] == "news")
    check(
        "/api/status shows the news run with failed sources and a next run",
        news_run["status"] == "PARTIAL"
        and news_run["meta"]["failed"] == ["C", "D"]
        and st["next_runs"].get("news") is not None,
    )
    check("failing sources degrade (not halt) the system", c.halt_reason is None)


async def scenario_all_fail(cfg: AppConfig) -> None:
    print("\n2. All sources failing")
    ncfg = news_config(cfg, ["A", "B"], stoplist=[])
    c = sf.make_controller(ncfg, sf.FakeFutures(), sf.FakeSpot())
    await c.universe_job()
    http = HttpClient(
        {},
        client=httpx.AsyncClient(
            transport=transport(
                {
                    "a.test": httpx.ConnectError("refused"),
                    "b.test": httpx.Response(503),
                }
            )
        ),
        sleep=lambda s: asyncio.sleep(0),
    )
    c.agents["news"] = NewsAgent(c.deps, RssClient(http))
    for _ in range(3):
        await c.news_job()
    st = await sf.api_status(ncfg)
    run = next(r for r in st["runs"] if r["agent"] == "news")
    check(
        "run FAILED and the error names both sources and the component",
        run["status"] == "FAILED"
        and run["error_component"] == "news"
        and "all 2 RSS sources failed" in (run["error_message"] or ""),
        str(run["error_message"]),
    )
    check(
        "news failures never halt the system",
        c.halt_reason is None and st["state"] != "HALTED",
        st["state"],
    )
    check("state is DEGRADED while news is failing", st["state"] == "DEGRADED", st["state"])
    check("news breaker opened after 3 failed runs", c.breakers["news"].is_open(sf_now()))


def sf_now() -> datetime:
    return datetime.now(UTC)


async def scenario_retention(cfg: AppConfig) -> None:
    print("\n3. Retention purges old news")
    c = sf.make_controller(cfg, sf.FakeFutures(), sf.FakeSpot())
    now = datetime.now(UTC)
    async with c.deps.session_factory() as s:
        s.add(
            NewsItem(
                source="X",
                title="old",
                url="https://x.test/old",
                symbols=[],
                fetched_at=now - timedelta(days=6),
            )
        )
        s.add(
            NewsItem(
                source="X",
                title="fresh",
                url="https://x.test/fresh",
                symbols=[],
                fetched_at=now - timedelta(hours=1),
            )
        )
        await s.commit()
    await c.retention_job()
    async with c.deps.session_factory() as s:
        left = (await s.execute(select(func.count()).select_from(NewsItem))).scalar_one()
        titles = list((await s.execute(select(NewsItem.title))).scalars())
        _ = ops
    check(
        "news older than 5 days purged, fresh kept", left == 1 and titles == ["fresh"], str(titles)
    )


async def main() -> int:
    cfg = load_config_or_exit()
    base_url = cfg.settings.database_url.get_secret_value()
    sim_url = await sf.make_sim_db(base_url)
    scfg = sf.sim_config(cfg, sim_url)
    dsn = asyncpg_dsn(sim_url)
    try:
        await scenario_mixed_sources(scfg, dsn)
        await sf.reset_sim_data(scfg)
        await scenario_all_fail(scfg)
        await sf.reset_sim_data(scfg)
        await scenario_retention(scfg)
    finally:
        for engine in sf.ENGINES:
            await engine.dispose()
        await sf.drop_sim_db(base_url)
    failed = [r for r in sf.RESULTS if not r[1]]
    print(f"\n{len(sf.RESULTS)} checks, {len(failed)} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
