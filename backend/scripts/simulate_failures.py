"""F5 acceptance: simulated failures behave per policy and /api/status reflects them.

Runs the real Controller and API against a throwaway database (created and dropped here) with
fake MEXC clients. Scenarios: MEXC unreachable, malformed response, DB down, cycle overrun,
plus HTTP retry behaviour. Public data only; no secrets are printed.

Run: uv run python scripts/simulate_failures.py
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import httpx
from pydantic import SecretStr
from sqlalchemy import func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from tss.agents.base import Deps
from tss.api.app import create_app
from tss.clients.http import HttpClient
from tss.clients.mexc_futures import MexcFuturesClient
from tss.clients.mexc_spot import MexcSpotClient
from tss.clients.models import ContractDetail, FuturesTicker, Kline, SpotKline, SpotTicker
from tss.control.pipeline import Controller
from tss.core.errors import DataSourceError
from tss.core.settings import AppConfig, load_config_or_exit
from tss.db.models import AgentRun
from tss.db.repositories import ops
from tss.db.session import create_engine, create_session_factory

BACKEND = Path(__file__).resolve().parents[1]
SIM_DB = "tss_sim"
RESULTS: list[tuple[str, bool, str]] = []
ENGINES: list[Any] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))


# --- fakes -------------------------------------------------------------------------------


class FakeFutures:
    """Healthy synthetic market of 3 liquid contracts; `fail` simulates MEXC being down."""

    def __init__(self) -> None:
        self.fail = False

    def _maybe_fail(self, op: str) -> None:
        if self.fail:
            raise DataSourceError("mexc_futures", "P1", op, "simulated: MEXC unreachable")

    async def contract_detail(self) -> list[ContractDetail]:
        self._maybe_fail("contract_detail")
        return [
            ContractDetail(
                symbol=s,
                baseCoin=s.split("_")[0],
                quoteCoin="USDT",
                settleCoin="USDT",
                contractSize=1.0,
                state=0,
                makerFeeRate=0.0002,
                takerFeeRate=0.0004,
            )
            for s in ("BTC_USDT", "ETH_USDT", "AAA_USDT")
        ]

    async def tickers(self) -> list[FuturesTicker]:
        self._maybe_fail("tickers")
        return [
            FuturesTicker(
                symbol=s,
                lastPrice=100.0,
                fairPrice=100.0,
                holdVol=1e6,
                fundingRate=0.0001,
                volume24=1e7,
                amount24=5e7,
            )
            for s in ("BTC_USDT", "ETH_USDT", "AAA_USDT")
        ]

    async def klines(
        self, symbol: str, interval: str, start: datetime, end: datetime
    ) -> list[Kline]:
        self._maybe_fail("klines")
        out: list[Kline] = []
        t = start.replace(second=0, microsecond=0)
        t = t.replace(minute=t.minute - t.minute % 15)
        while t <= end:
            out.append(
                Kline(
                    open_time=t,
                    open=100.0,
                    high=101.0,
                    low=99.0,
                    close=100.0,
                    volume=10.0,
                    amount=1000.0,
                )
            )
            t = t.fromtimestamp(t.timestamp() + 900, tz=UTC)
        return out


class FakeSpot:
    async def tickers_24h(self) -> list[SpotTicker]:
        return [
            SpotTicker(symbol=f"{b}USDT", lastPrice=100.0, quoteVolume=1e7)
            for b in ("BTC", "ETH", "AAA")
        ]

    async def klines_15m(self, spot_symbol: str, limit: int) -> list[SpotKline]:
        return []


# --- harness -----------------------------------------------------------------------------


async def admin_sql(base_url: str, *statements: str) -> None:
    """Run CREATE/DROP DATABASE statements on the dev server (autocommit)."""
    engine = create_async_engine(base_url, isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as conn:
            for stmt in statements:
                await conn.execute(text(stmt))
    finally:
        await engine.dispose()


async def make_sim_db(base_url: str) -> str:
    url = make_url(base_url)
    await admin_sql(
        base_url, f'DROP DATABASE IF EXISTS "{SIM_DB}" WITH (FORCE)', f'CREATE DATABASE "{SIM_DB}"'
    )
    sim_url = url.set(database=SIM_DB).render_as_string(hide_password=False)
    env = {**os.environ, "DATABASE_URL": sim_url}
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND,
        env=env,
        check=True,
        capture_output=True,
    )
    return sim_url


async def drop_sim_db(base_url: str) -> None:
    await admin_sql(base_url, f'DROP DATABASE IF EXISTS "{SIM_DB}" WITH (FORCE)')


def sim_config(cfg: AppConfig, sim_url: str) -> AppConfig:
    settings = cfg.settings.model_copy(update={"database_url": SecretStr(sim_url)})
    return AppConfig(
        settings=settings,
        thresholds=cfg.thresholds,
        denylist=cfg.denylist,
        news_sources=cfg.news_sources,
    )


async def api_status(cfg: AppConfig) -> dict[str, Any]:
    app = create_app(cfg)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://sim") as client:
            resp = await client.get("/api/status")
            body = cast("dict[str, Any]", resp.json())
            body["_http"] = resp.status_code
            return body


async def api_get(cfg: AppConfig, path: str) -> tuple[int, dict[str, Any]]:
    app = create_app(cfg)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://sim") as client:
            resp = await client.get(path)
            return resp.status_code, cast("dict[str, Any]", resp.json())


def make_controller(cfg: AppConfig, futures: Any, spot: Any) -> Controller:
    engine = create_engine(cfg.settings)
    ENGINES.append(engine)
    deps = Deps(
        config=cfg,
        session_factory=create_session_factory(engine),
        futures=cast("MexcFuturesClient", futures),
        spot=cast("MexcSpotClient", spot),
    )
    return Controller(deps)


async def state_of(c: Controller) -> str | None:
    async with c.deps.session_factory() as s:
        st = await ops.get_system_state(s)
        return st.state if st else None


# --- scenarios ---------------------------------------------------------------------------


async def scenario_mexc_unreachable(cfg: AppConfig) -> None:
    print("\n1. MEXC unreachable")
    fake = FakeFutures()
    c = make_controller(cfg, fake, FakeSpot())
    await c.universe_job()
    await c.snapshot_job()
    check("healthy start: not halted", c.halt_reason is None)
    fake.fail = True
    for i in range(1, 4):
        await c.snapshot_job()
        if i < 3:
            check(f"failure {i}: not halted yet (breaker opens after 3)", c.halt_reason is None)
            check(
                f"failure {i}: state DEGRADED",
                await state_of(c) == "DEGRADED",
                str(await state_of(c)),
            )
    check(
        "3 failures: HALTED (MEXC futures breaker open)",
        c.halt_reason == "MEXC futures breaker open",
        str(c.halt_reason),
    )
    check("system_state row is HALTED", await state_of(c) == "HALTED")
    st = await api_status(cfg)
    check("/api/status reports HALTED", st.get("state") == "HALTED", str(st.get("reason")))
    runs = {r["agent"]: r for r in st["runs"]}
    err = runs["snapshot"]["error_message"] or ""
    check(
        "snapshot run FAILED with component named",
        runs["snapshot"]["status"] == "FAILED"
        and runs["snapshot"]["error_component"] == "mexc_futures",
        err,
    )
    before = (await api_status(cfg))["runs"]
    await c.snapshot_job()  # halted: dependent jobs stop
    after = (await api_status(cfg))["runs"]
    check("halted: dependent jobs do not run", before == after)
    fake.fail = False
    await c.recovery_job()
    check("recovery (60 s poll) clears the halt", c.halt_reason is None)
    check("state leaves HALTED", await state_of(c) != "HALTED", str(await state_of(c)))


async def scenario_malformed(cfg: AppConfig) -> None:
    print("\n2. Malformed response")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/contract/detail"):
            bad = {
                "success": True,
                "code": 0,
                "data": [
                    {
                        "symbol": "BTC_USDT",
                        "baseCoin": "BTC",
                        "quoteCoin": "USDT",
                        "settleCoin": "USDT",
                        "state": 0,
                    }
                ],
            }  # contractSize missing
            return httpx.Response(200, json=bad)
        return httpx.Response(404)

    http = HttpClient({}, client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    futures = MexcFuturesClient(http)
    c = make_controller(cfg, futures, FakeSpot())
    await c.universe_job()
    st = await api_status(cfg)
    uni = next(r for r in st["runs"] if r["agent"] == "universe")
    msg = uni["error_message"] or ""
    check(
        "run FAILED, error names the field",
        uni["status"] == "FAILED" and "contractSize" in msg,
        msg,
    )
    check("error names component", uni["error_component"] == "mexc_futures")
    check(
        "one failure does not halt; state DEGRADED",
        c.halt_reason is None and await state_of(c) == "DEGRADED",
        str(await state_of(c)),
    )
    await http.aclose()


async def scenario_http_retry() -> None:
    print("\n3. HTTP retry policy")
    calls = {"n": 0}
    sleeps: list[float] = []

    async def fake_sleep(s: float) -> None:
        sleeps.append(s)

    def flaky(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, headers={"Retry-After": "3"})
        if calls["n"] == 2:
            return httpx.Response(503)
        return httpx.Response(200, json={"ok": True})

    http = HttpClient(
        {},
        client=httpx.AsyncClient(transport=httpx.MockTransport(flaky)),
        sleep=fake_sleep,
        jitter=lambda: 0.0,
    )
    body = await http.get_json("https://x.test/a", component="t", operation="op")
    check("recovers after 429 + 503", body == {"ok": True} and calls["n"] == 3)
    check("honours Retry-After, then 4 s backoff", sleeps == [3.0, 4.0], str(sleeps))

    calls["n"] = 0
    sleeps.clear()
    http2 = HttpClient(
        {},
        client=httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(500))),
        sleep=fake_sleep,
        jitter=lambda: 0.0,
    )
    try:
        await http2.get_json("https://x.test/b?secret=1", component="t", operation="op")
        check("persistent 5xx raises", False)
    except DataSourceError as exc:
        check("persistent 5xx: 4 attempts, backoff 2/4/8", sleeps == [2.0, 4.0, 8.0], str(sleeps))
        check(
            "error has component/phase/op, no query string",
            (exc.component, exc.phase, exc.operation) == ("t", "P1", "op")
            and "secret" not in str(exc)
            and "secret" not in str(exc.context),
            exc.message,
        )

    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    http3 = HttpClient(
        {},
        client=httpx.AsyncClient(transport=httpx.MockTransport(refuse)),
        sleep=fake_sleep,
        jitter=lambda: 0.0,
    )
    try:
        await http3.get_json("https://x.test/c", component="t", operation="op")
        check("network error raises", False)
    except DataSourceError as exc:
        check(
            "network errors are retried then reported", "ConnectError" in exc.message, exc.message
        )


async def scenario_db_down(cfg: AppConfig, sim_url: str) -> None:
    print("\n4. Database down")
    good = make_controller(cfg, FakeFutures(), FakeSpot())
    await good.universe_job()
    bad_url = make_url(sim_url).set(port=1).render_as_string(hide_password=False)  # nothing listens
    bad_engine = create_engine(cfg.settings.model_copy(update={"database_url": SecretStr(bad_url)}))
    bad_factory = create_session_factory(bad_engine)
    good_factory = good.deps.session_factory
    good.deps.session_factory = bad_factory
    await good.snapshot_job()
    check(
        "DB unreachable: critical HALT",
        good.halt_reason is not None and "database unreachable" in good.halt_reason,
        str(good.halt_reason),
    )
    bad_cfg = sim_config(cfg, bad_url)
    app = create_app(bad_cfg)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://sim") as client:
            health = await client.get("/api/health")
            stat = await client.get("/api/status")
    check(
        "/api/health returns 503 while DB is down",
        health.status_code == 503,
        health.json().get("error", ""),
    )
    err = stat.json().get("error", {})
    check(
        "/api/status returns the error envelope (503) naming the component",
        stat.status_code == 503
        and err.get("component") == "api"
        and "database" in err.get("message", ""),
        str(err),
    )
    good.deps.session_factory = good_factory  # DB comes back
    await good.recovery_job()
    check("recovery poll clears the halt once DB is back", good.halt_reason is None)
    st = await api_status(cfg)
    check("/api/status leaves HALTED", st["state"] != "HALTED", st["state"])
    await bad_engine.dispose()


async def scenario_overrun(cfg: AppConfig) -> None:
    print("\n5. Cycle overrun")
    c = make_controller(cfg, FakeFutures(), FakeSpot())
    await c.universe_job()
    await c.snapshot_job()
    c.budget_s = 0  # every cycle overruns
    await asyncio.gather(c.pipeline_job(), c.pipeline_job())  # second must be skipped
    st = await api_status(cfg)
    pipes = [r for r in st["runs"] if r["agent"] == "pipeline"]
    meta = pipes[0]["meta"] if pipes else {}
    check(
        "overrun is flagged in the pipeline run and the cycle still completes",
        bool(pipes)
        and meta.get("overrun") is True
        and pipes[0]["status"] in ("SUCCESS", "PARTIAL"),
        str(meta),
    )
    async with c.deps.session_factory() as s:
        n = (
            await s.execute(
                select(func.count()).select_from(AgentRun).where(AgentRun.agent == "pipeline")
            )
        ).scalar_one()
    check("max_instances=1: overlapping start was skipped (1 pipeline run)", n == 1, f"runs={n}")
    check("system not halted by an overrun", c.halt_reason is None)


async def scenario_retention(cfg: AppConfig) -> None:
    print("\n6. Retention purge (F11)")
    from datetime import timedelta

    from tss.core.time import utc_now
    from tss.db.models import (
        Classification,
        DailyOpen,
        Kline15m,
        MarketMover,
        MarketSnapshot,
        MomentumRanking,
    )

    c = make_controller(cfg, FakeFutures(), FakeSpot())
    now = utc_now()
    old, fresh = now - timedelta(days=6), now - timedelta(hours=1)
    keep = cfg.thresholds.kline.backfill_bars
    cycle = uuid.uuid4()
    async with c.deps.session_factory() as s:
        for ts in (old, fresh):
            s.add(MarketSnapshot(symbol="X_USDT", ts=ts, liquid=True))
            s.add(MarketMover(ts=ts, side="GAINER", rank=1, symbol="X_USDT"))
            s.add(
                MomentumRanking(
                    cycle_id=uuid.uuid4(),
                    symbol="X_USDT",
                    ts=ts,
                    pool_rank=1,
                    passed_gate2=False,
                    pinned=False,
                )
            )
            s.add(
                Classification(
                    cycle_id=cycle if ts == fresh else uuid.uuid4(),
                    symbol="X_USDT",
                    window="1h",
                    ts=ts,
                    state="NEUTRAL",
                    flags=[],
                    unreliable_reasons=[],
                )
            )
        s.add(DailyOpen(symbol="X_USDT", utc_date=(old).date(), open=1.0))
        s.add(DailyOpen(symbol="X_USDT", utc_date=now.date(), open=1.0))
        base = now - timedelta(days=10)  # 400 bars, all older than the 5-day cutoff
        for i in range(400):
            s.add(
                Kline15m(
                    symbol="X_USDT",
                    open_time=base + timedelta(minutes=15 * i),
                    open=1,
                    high=1,
                    low=1,
                    close=1,
                    volume=1,
                    amount=1,
                )
            )
        for i in range(10):  # recent bars survive regardless
            s.add(
                Kline15m(
                    symbol="X_USDT",
                    open_time=now - timedelta(minutes=15 * (i + 2)),
                    open=1,
                    high=1,
                    low=1,
                    close=1,
                    volume=1,
                    amount=1,
                )
            )
        await s.commit()
    await c.retention_job()
    async with c.deps.session_factory() as s:

        async def count(model: Any, col: Any, cutoff: Any) -> int:
            return int(
                (
                    await s.execute(select(func.count()).select_from(model).where(col < cutoff))
                ).scalar_one()
            )

        cutoff = now - timedelta(days=cfg.settings.retention_days)
        check(
            "snapshots: none older than 5 days",
            await count(MarketSnapshot, MarketSnapshot.ts, cutoff) == 0,
        )
        check(
            "movers/momentum/classification: none older than 5 days",
            await count(MarketMover, MarketMover.ts, cutoff) == 0
            and await count(MomentumRanking, MomentumRanking.ts, cutoff) == 0
            and await count(Classification, Classification.ts, cutoff) == 0,
        )
        check(
            "daily_opens: old day purged, today kept",
            await count(DailyOpen, DailyOpen.utc_date, cutoff.date()) == 0
            and int((await s.execute(select(func.count()).select_from(DailyOpen))).scalar_one())
            == 1,
        )
        total = int((await s.execute(select(func.count()).select_from(Kline15m))).scalar_one())
        old_left = await count(Kline15m, Kline15m.open_time, cutoff)
        check(
            "klines: only the newest backfill_bars (floor) survive for the symbol",
            total == keep,
            f"total={total}, floor={keep}",
        )
        check(
            "klines: bars older than the cutoff that remain = floor - recent bars",
            old_left == keep - 10,
            f"old_left={old_left}",
        )
        fresh_snap = int(
            (await s.execute(select(func.count()).select_from(MarketSnapshot))).scalar_one()
        )
        check("fresh rows are untouched", fresh_snap == 1)
        size = await ops.db_size_bytes(s)
        check("DB size is reported", size > 0, f"{size} bytes")
    st = await api_status(cfg)
    check("/api/status exposes db_size_bytes", st.get("db_size_bytes", 0) > 0)


async def scenario_classification_e2e(cfg: AppConfig) -> None:
    print("\n7. Classification end to end (synthetic 4.5 h history)")
    from datetime import timedelta

    from tss.core.time import floor_to_minutes, utc_now
    from tss.db.models import Classification, Kline15m, MarketSnapshot

    c = make_controller(cfg, FakeFutures(), FakeSpot())
    await c.universe_job()  # contracts BTC/ETH (pinned) + AAA
    now = utc_now()
    expected = floor_to_minutes(now, 15) - timedelta(minutes=15)
    newest_snap = floor_to_minutes(now, 5)
    steps = 54  # 4.5 h of 5-min snapshots
    # BTC rises steadily; ETH rises for 3 h then falls in the last hour (1h bearish, 4h bullish)
    btc_close = [100.0 + i for i in range(33)]
    eth_close = [100.0 + i for i in range(29)] + [127.0, 126.0, 125.0, 124.0]
    async with c.deps.session_factory() as s:
        for sym, closes, f0, fstep in (
            ("BTC_USDT", btc_close, 0.0001, 0.000001),
            ("ETH_USDT", eth_close, 0.0001, -0.000001),
        ):
            for i, close in enumerate(closes):
                s.add(
                    Kline15m(
                        symbol=sym,
                        open_time=expected - timedelta(minutes=15 * (32 - i)),
                        open=close,
                        high=close,
                        low=close,
                        close=close,
                        volume=1.0,
                        amount=1000.0 + 10 * i,
                    )
                )
            for k in range(steps):
                s.add(
                    MarketSnapshot(
                        symbol=sym,
                        ts=newest_snap - timedelta(minutes=5 * (steps - 1 - k)),
                        last_price=closes[-1],
                        hold_vol=1e6 * (1 + 0.001 * k),
                        funding_rate=f0 + fstep * k,
                        liquid=True,
                    )
                )
        await s.commit()
    outcome = await c.agents["classification"].execute(uuid.uuid4(), now)
    check("classification run succeeded", outcome.status == "SUCCESS", outcome.status)
    async with c.deps.session_factory() as s:
        rows = {
            (r.symbol, r.window): r for r in (await s.execute(select(Classification))).scalars()
        }
    btc1, btc4 = rows[("BTC_USDT", "1h")], rows[("BTC_USDT", "4h")]
    eth1, eth4 = rows[("ETH_USDT", "1h")], rows[("ETH_USDT", "4h")]
    check(
        "BTC 1h/4h = LONG_BUILDUP",
        (btc1.state, btc4.state) == ("LONG_BUILDUP", "LONG_BUILDUP"),
        f"{btc1.state}/{btc4.state} reasons={btc1.unreliable_reasons}",
    )
    check(
        "BTC 1h price change = close[-1]/close[-5]-1",
        abs((btc1.price_change_pct or 0) - (132 / 128 - 1) * 100) < 1e-9,
    )
    k = steps - 1
    expect_oi_1h = ((1 + 0.001 * k) / (1 + 0.001 * (k - 12)) - 1) * 100
    check(
        "BTC 1h OI change uses the snapshot exactly 1 h earlier",
        abs((btc1.oi_change_pct or 0) - expect_oi_1h) < 1e-9,
        f"{btc1.oi_change_pct}",
    )
    check(
        "BTC funding delta positive and FUNDING_CONFIRMS set",
        (btc1.funding_delta or 0) > 0 and "FUNDING_CONFIRMS" in btc1.flags,
        str(btc1.flags),
    )
    check(
        "BTC no TF_CONFLICT, LIQUIDATIONS_UNAVAILABLE always set",
        "TF_CONFLICT" not in btc1.flags and "LIQUIDATIONS_UNAVAILABLE" in btc1.flags,
    )
    check(
        "ETH 1h SHORT_BUILDUP, 4h LONG_BUILDUP",
        (eth1.state, eth4.state) == ("SHORT_BUILDUP", "LONG_BUILDUP"),
        f"{eth1.state}/{eth4.state}",
    )
    check(
        "ETH TF_CONFLICT on both windows",
        "TF_CONFLICT" in eth1.flags and "TF_CONFLICT" in eth4.flags,
    )
    check(
        "ETH FUNDING_CONFIRMS on SHORT_BUILDUP (funding falling)", "FUNDING_CONFIRMS" in eth1.flags
    )
    check(
        "no spot market data -> spot change is NULL, no SPOT_CONFIRMED",
        btc1.spot_volume_change_pct is None and "SPOT_CONFIRMED" not in btc1.flags,
    )
    check(
        "no WARMING_UP: history covers 4 h",
        "WARMING_UP" not in btc4.flags and "WARMING_UP" not in eth4.flags,
    )


async def main() -> int:
    cfg = load_config_or_exit()
    base_url = cfg.settings.database_url.get_secret_value()
    sim_url = await make_sim_db(base_url)
    scfg = sim_config(cfg, sim_url)
    try:
        await scenario_mexc_unreachable(scfg)
        await reset_sim_data(scfg)
        await scenario_malformed(scfg)
        await scenario_http_retry()
        await reset_sim_data(scfg)
        await scenario_db_down(scfg, sim_url)
        await reset_sim_data(scfg)
        await scenario_overrun(scfg)
        await reset_sim_data(scfg)
        await scenario_retention(scfg)
        await reset_sim_data(scfg)
        await scenario_classification_e2e(scfg)
    finally:
        for engine in ENGINES:
            await engine.dispose()
        await drop_sim_db(base_url)
    failed = [r for r in RESULTS if not r[1]]
    print(f"\n{len(RESULTS)} checks, {len(failed)} failed")
    return 1 if failed else 0


async def reset_sim_data(scfg: AppConfig) -> None:
    """Empty the throwaway database between scenarios. Refuses to touch any other database."""
    name = make_url(scfg.settings.database_url.get_secret_value()).database
    if name != SIM_DB:
        raise RuntimeError(f"refusing to truncate database {name!r}; only {SIM_DB!r} is allowed")
    engine = create_engine(scfg.settings)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "TRUNCATE agent_runs, system_state, market_snapshots, "
                    "klines_15m, daily_opens, momentum_rankings, classifications, "
                    "market_movers, contracts"
                )
            )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
