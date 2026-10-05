"""F10 acceptance: the Notifier agent against a fake Telegram server (throwaway database).

Covers: exactly-once delivery (incl. two agents racing), only BUY/SELL/bullT/bearT, stale events
skipped, message content, release + retry after failures (5xx, network, 401, flood control),
pacing (>= 1.1 s between messages), per-run cap, "not configured", the Controller hook and that
no token reaches the database. No network access; the token below is fake.

Run: uv run python scripts/simulate_telegram.py
"""

from __future__ import annotations

import asyncio
import json
import sys
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from pydantic import SecretStr
from sqlalchemy import func, select, text

import simulate_failures as sf
from tss.agents.base import SUCCESS, AgentResult, BaseAgent
from tss.agents.notifier import NotifierAgent
from tss.clients.telegram import TelegramClient
from tss.core.settings import AppConfig, load_config_or_exit
from tss.db.models import MarketSnapshot, SignalEvent

check = sf.check
TOKEN = "999:SECRET-SIM-TOKEN"


class FakeTelegram:
    """Records delivered messages; `behaviour(n)` decides the response for the n-th request."""

    def __init__(self) -> None:
        self.delivered: list[str] = []
        self.requests = 0
        self.behaviour: Callable[[int], httpx.Response | Exception | None] = lambda n: None
        self.sleeps: list[float] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests += 1
        assert request.url.path == f"/bot{TOKEN}/sendMessage"
        outcome = self.behaviour(self.requests)
        if isinstance(outcome, Exception):
            raise outcome
        if outcome is not None:
            return outcome
        self.delivered.append(json.loads(request.content)["text"])
        return httpx.Response(200, json={"ok": True, "result": {"message_id": len(self.delivered)}})

    def client(self) -> TelegramClient:
        return TelegramClient(
            SecretStr(TOKEN),
            "42",
            client=httpx.AsyncClient(transport=httpx.MockTransport(self.handler)),
        )

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)


def event(
    symbol: str, tf: str, name: str, closed: datetime, against: bool | None = False
) -> SignalEvent:
    return SignalEvent(
        symbol=symbol, timeframe=tf, bar_close_time=closed, event=name, against_htf=against
    )


async def add(c: Any, rows: list[SignalEvent]) -> None:
    async with c.deps.session_factory() as s:
        s.add_all(rows)
        await s.commit()


async def notified(c: Any) -> dict[str, bool]:
    async with c.deps.session_factory() as s:
        rows = (await s.execute(select(SignalEvent))).scalars()
        return {f"{r.symbol}/{r.timeframe}/{r.event}": r.notified_at is not None for r in rows}


def agent_for(c: Any, tg: FakeTelegram, **kw: Any) -> NotifierAgent:
    return NotifierAgent(c.deps, tg.client(), sleep=tg.sleep, **kw)


async def seed_price(c: Any, now: datetime) -> None:
    async with c.deps.session_factory() as s:
        s.add(
            MarketSnapshot(
                symbol="BTC_USDT", ts=now - timedelta(minutes=2), last_price=85913.4, liquid=True
            )
        )
        await s.commit()


async def scenario_exactly_once(cfg: AppConfig) -> None:
    print("\n1. Exactly once, event types, staleness, content")
    c = sf.make_controller(cfg, sf.FakeFutures(), sf.FakeSpot())
    now = datetime.now(UTC).replace(microsecond=0)
    closed = now - timedelta(minutes=1)
    await seed_price(c, now)
    await add(
        c,
        [
            event("BTC_USDT", "5m", "BUY", closed, True),
            event("ETH_USDT", "5m", "SELL", closed, False),
            event("BTC_USDT", "15m", "BULL_T", closed, False),
            event("ETH_USDT", "15m", "BEAR_T", closed, None),
            event("BTC_USDT", "1h", "TD_BULL", closed, None),
            event("ETH_USDT", "1h", "TD_BEAR", closed, None),
            event(
                "AAA_USDT", "5m", "BUY", now - timedelta(minutes=40), False
            ),  # stale: 5m window is 15 min
        ],
    )
    tg = FakeTelegram()
    agent = agent_for(c, tg)
    out = await agent.execute(uuid.uuid4(), now)
    meta = (out.result.meta if out.result else {}) or {}
    check(
        "run SUCCESS and sent 4 (BUY, SELL, bullT, bearT only)",
        out.status == "SUCCESS" and meta["sent"] == 4 and len(tg.delivered) == 4,
        str(meta),
    )
    flags = await notified(c)
    check(
        "TD events and the stale event are not sent and stay unnotified",
        not flags["BTC_USDT/1h/TD_BULL"]
        and not flags["ETH_USDT/1h/TD_BEAR"]
        and not flags["AAA_USDT/5m/BUY"],
    )
    check(
        "the four delivered events are marked notified once",
        all(
            flags[k]
            for k in (
                "BTC_USDT/5m/BUY",
                "ETH_USDT/5m/SELL",
                "BTC_USDT/15m/BULL_T",
                "ETH_USDT/15m/BEAR_T",
            )
        ),
    )
    first = next(m for m in tg.delivered if "BUY" in m)
    check(
        "message has symbol, timeframe, event, against-4H tag, price, IST bar time, disclaimer",
        all(
            x in first
            for x in (
                "BTC_USDT",
                "5m",
                "BUY",
                "Against the 4H trend",
                "85,913.40",
                "IST",
                "Not financial advice",
            )
        ),
        first.replace("\n", " | "),
    )
    check(
        "no secret in any message", all(TOKEN not in m and "SECRET" not in m for m in tg.delivered)
    )
    again = await agent.execute(uuid.uuid4(), now + timedelta(seconds=30))
    check(
        "second run sends nothing: each event exactly once",
        again.result is not None and again.result.rows_out == 0 and len(tg.delivered) == 4,
    )
    check(
        "pacing: >= 1.1 s between consecutive messages",
        tg.sleeps == [1.1, 1.1, 1.1],
        str(tg.sleeps),
    )


async def scenario_concurrency(cfg: AppConfig) -> None:
    print("\n2. Two agents racing")
    c = sf.make_controller(cfg, sf.FakeFutures(), sf.FakeSpot())
    now = datetime.now(UTC).replace(microsecond=0)
    await add(
        c, [event(f"S{i:02d}_USDT", "5m", "BUY", now - timedelta(minutes=1)) for i in range(12)]
    )
    tg = FakeTelegram()
    a, b = agent_for(c, tg), agent_for(c, tg)
    await asyncio.gather(a.execute(uuid.uuid4(), now), b.execute(uuid.uuid4(), now))
    names = sorted(m.split("·")[1].strip() for m in tg.delivered)
    check(
        "12 events delivered exactly once by two concurrent agents (no duplicates, none lost)",
        len(tg.delivered) == 12 and len(set(names)) == 12,
        f"{len(tg.delivered)} sent, {len(set(names))} unique",
    )


async def scenario_failures(cfg: AppConfig) -> None:
    print("\n3. Failures are released and retried exactly once")
    c = sf.make_controller(cfg, sf.FakeFutures(), sf.FakeSpot())
    now = datetime.now(UTC).replace(microsecond=0)
    await add(c, [event(f"F{i}_USDT", "5m", "SELL", now - timedelta(minutes=1)) for i in range(5)])
    tg = FakeTelegram()
    tg.behaviour = lambda n: httpx.Response(502, json={}) if n == 3 else None
    agent = agent_for(c, tg)
    out = await agent.execute(uuid.uuid4(), now)
    meta = (out.result.meta if out.result else {}) or {}
    check(
        "a 5xx mid-run gives PARTIAL: 2 sent, 3 released",
        out.status == "PARTIAL" and meta["sent"] == 2 and meta["released"] == 3,
        str(meta),
    )
    flags = await notified(c)
    check(
        "released events are unnotified again, delivered ones stay notified",
        sum(flags.values()) == 2,
        str(flags),
    )
    tg.behaviour = lambda n: None
    await agent.execute(uuid.uuid4(), now + timedelta(minutes=5))
    check(
        "next run delivers the remaining 3: 5 messages in total, none twice",
        len(tg.delivered) == 5 and len({m for m in tg.delivered}) == 5,
        f"{len(tg.delivered)} sent",
    )

    # everything fails -> FAILED, nothing lost
    c2 = sf.make_controller(cfg, sf.FakeFutures(), sf.FakeSpot())
    await sf.reset_sim_data(cfg)
    await add(
        c2,
        [
            event("N1_USDT", "5m", "BUY", now - timedelta(minutes=1)),
            event("N2_USDT", "5m", "BUY", now - timedelta(minutes=1)),
        ],
    )
    tg2 = FakeTelegram()
    tg2.behaviour = lambda n: httpx.ConnectError("boom " + f"https://api.telegram.org/bot{TOKEN}/x")
    out2 = await agent_for(c2, tg2).execute(uuid.uuid4(), now)
    flags2 = await notified(c2)
    check(
        "network failure: run FAILED, error names component, nothing marked notified",
        out2.status == "FAILED"
        and out2.error is not None
        and out2.error.component == "telegram"
        and not any(flags2.values()),
        str(out2.error and out2.error.message),
    )
    check(
        "the error does not contain the token or the URL",
        out2.error is not None
        and TOKEN not in out2.error.message
        and "api.telegram.org" not in out2.error.message,
    )
    tg2.behaviour = lambda n: None
    await agent_for(c2, tg2).execute(uuid.uuid4(), now + timedelta(minutes=5))
    check("after recovery both events are delivered once", len(tg2.delivered) == 2)


async def scenario_flood_and_permanent(cfg: AppConfig) -> None:
    print("\n4. Flood control and permanent errors")
    c = sf.make_controller(cfg, sf.FakeFutures(), sf.FakeSpot())
    now = datetime.now(UTC).replace(microsecond=0)
    await add(c, [event(f"R{i}_USDT", "5m", "BUY", now - timedelta(minutes=1)) for i in range(3)])
    tg = FakeTelegram()
    tg.behaviour = lambda n: (
        httpx.Response(
            429,
            json={
                "ok": False,
                "description": "Too Many Requests",
                "parameters": {"retry_after": 3},
            },
        )
        if n == 2
        else None
    )
    out = await agent_for(c, tg).execute(uuid.uuid4(), now)
    check(
        "429 with a short retry_after: waits retry_after + 0.5 s and retries once, all delivered",
        out.status == "SUCCESS" and len(tg.delivered) == 3 and 3.5 in tg.sleeps,
        str(tg.sleeps),
    )

    c2 = sf.make_controller(cfg, sf.FakeFutures(), sf.FakeSpot())
    await sf.reset_sim_data(cfg)
    await add(c2, [event(f"L{i}_USDT", "5m", "SELL", now - timedelta(minutes=1)) for i in range(3)])
    tg2 = FakeTelegram()
    tg2.behaviour = lambda n: (
        httpx.Response(
            429,
            json={
                "ok": False,
                "description": "Too Many Requests",
                "parameters": {"retry_after": 120},
            },
        )
        if n >= 2
        else None
    )
    out2 = await agent_for(c2, tg2).execute(uuid.uuid4(), now)
    flags = await notified(c2)
    check(
        "429 with a long retry_after: stops, releases the rest (1 sent, 2 retried later)",
        out2.status == "PARTIAL" and len(tg2.delivered) == 1 and sum(flags.values()) == 1,
        str(flags),
    )

    c3 = sf.make_controller(cfg, sf.FakeFutures(), sf.FakeSpot())
    await sf.reset_sim_data(cfg)
    await add(c3, [event("P1_USDT", "5m", "BUY", now - timedelta(minutes=1))])
    tg3 = FakeTelegram()
    tg3.behaviour = lambda n: httpx.Response(
        401, json={"ok": False, "description": f"Unauthorized {TOKEN}"}
    )
    out3 = await agent_for(c3, tg3).execute(uuid.uuid4(), now)
    check(
        "permanent error (401): FAILED, event released for retry after the fix, token redacted",
        out3.status == "FAILED"
        and not any((await notified(c3)).values())
        and out3.error is not None
        and TOKEN not in out3.error.message
        and "***" in out3.error.message,
        str(out3.error and out3.error.message),
    )
    tg3.behaviour = lambda n: None
    await agent_for(c3, tg3).execute(uuid.uuid4(), now + timedelta(minutes=5))
    check("after the token is fixed the event is delivered once", len(tg3.delivered) == 1)


async def scenario_cap_and_config(cfg: AppConfig) -> None:
    print("\n5. Per-run cap, not configured, Controller hook, status")
    c = sf.make_controller(cfg, sf.FakeFutures(), sf.FakeSpot())
    now = datetime.now(UTC).replace(microsecond=0)
    await add(
        c, [event(f"C{i:02d}_USDT", "5m", "BUY", now - timedelta(minutes=1)) for i in range(25)]
    )
    tg = FakeTelegram()
    agent = agent_for(c, tg)
    await agent.execute(uuid.uuid4(), now)
    first = len(tg.delivered)
    await agent.execute(uuid.uuid4(), now + timedelta(seconds=30))
    check(
        "per-run cap 20: 20 on the first run, the other 5 on the next",
        (first, len(tg.delivered)) == (20, 25),
        f"{first} then {len(tg.delivered)}",
    )

    off = NotifierAgent(c.deps, None)
    out = await off.execute(uuid.uuid4(), now)
    check(
        "not configured: SKIPPED, nothing claimed",
        out.status == "SKIPPED"
        and out.result is not None
        and out.result.meta["reason"] == "telegram_not_configured",
    )

    # Controller hook: the notifier runs after every successful signal run when Telegram is enabled
    class StubSignal(BaseAgent):
        name = "signal"
        critical = False

        async def run(self, cycle_id: uuid.UUID, now: datetime) -> AgentResult:
            return AgentResult(status=SUCCESS)

    await sf.reset_sim_data(cfg)
    c2 = sf.make_controller(cfg, sf.FakeFutures(), sf.FakeSpot())
    await add(c2, [event("H1_USDT", "5m", "BUY", datetime.now(UTC) - timedelta(minutes=1))])
    tg2 = FakeTelegram()
    c2.agents["signal"] = StubSignal(c2.deps)
    c2.agents["notifier"] = agent_for(c2, tg2)
    c2.telegram_enabled = False
    await c2.signal_job()
    check("Telegram disabled: the notifier is not run after signals", len(tg2.delivered) == 0)
    c2.telegram_enabled = True
    await c2.signal_job()
    check("Telegram enabled: the notifier runs right after the signal run", len(tg2.delivered) == 1)

    st = await sf.api_status(cfg)
    check(
        "/api/status reports telegram_configured=false without credentials",
        st.get("telegram_configured") is False,
    )
    on_settings = cfg.settings.model_copy(
        update={"telegram_bot_token": SecretStr("1:x"), "telegram_chat_id": "42"}
    )
    on_cfg = AppConfig(
        settings=on_settings,
        thresholds=cfg.thresholds,
        denylist=cfg.denylist,
        news_sources=cfg.news_sources,
    )
    check(
        "/api/status reports telegram_configured=true when both values are set",
        (await sf.api_status(on_cfg)).get("telegram_configured") is True,
    )
    empty = cfg.settings.model_copy(
        update={"telegram_bot_token": SecretStr(""), "telegram_chat_id": "42"}
    )
    check("an empty token counts as not configured", empty.telegram_enabled is False)

    async with c2.deps.session_factory() as s:
        leaked = (
            await s.execute(
                text(
                    "select count(*) from agent_runs "
                    "where meta::text like '%SECRET%' or error_message like '%SECRET%'"
                )
            )
        ).scalar_one()
        n_runs = (await s.execute(select(func.count()).select_from(SignalEvent))).scalar_one()
        _ = n_runs
    check("no token in any agent_runs row", leaked == 0, f"{leaked} rows")


async def main() -> int:
    cfg = load_config_or_exit()
    base_url = cfg.settings.database_url.get_secret_value()
    sim_url = await sf.make_sim_db(base_url)
    scfg = sf.sim_config(cfg, sim_url)
    try:
        for scenario in (
            scenario_exactly_once,
            scenario_concurrency,
            scenario_failures,
            scenario_flood_and_permanent,
            scenario_cap_and_config,
        ):
            await sf.reset_sim_data(scfg)
            await scenario(scfg)
    finally:
        for engine in sf.ENGINES:
            await engine.dispose()
        await sf.drop_sim_db(base_url)
    failed = [r for r in sf.RESULTS if not r[1]]
    print(f"\n{len(sf.RESULTS)} checks, {len(failed)} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
