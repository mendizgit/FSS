"""F9 acceptance: the Signal agent on deterministic synthetic klines (throwaway database).

Checks: no signal on a forming bar, bar-cache efficiency, idempotency (also across an agent
restart), skipped symbols (short history, stale bars), partial failure, NOTIFY signal_new,
/api/signals/latest (order, fields) and retention. No network access, no secrets.

Run: uv run python scripts/simulate_signals.py
"""

from __future__ import annotations

import asyncio
import json
import math
import random
import sys
import uuid
from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any

import asyncpg  # type: ignore[import-untyped]
from sqlalchemy import func, select

import simulate_failures as sf
from tss.agents.setup import SetupAgent
from tss.agents.signal import SignalAgent, floor_to
from tss.clients.models import Kline
from tss.core.errors import DataSourceError
from tss.core.settings import AppConfig, load_config_or_exit
from tss.db.models import MomentumRanking, Signal, SignalEvent, SignalSetup
from tss.realtime.notify import asyncpg_dsn

check = sf.check
SECONDS = {"Min5": 300, "Min15": 900, "Min60": 3600, "Hour4": 14400}
ORIGIN = datetime(2026, 8, 1, tzinfo=UTC)
NOW = datetime(2026, 10, 5, 10, 5, 30, tzinfo=UTC)  # 5-min boundary + 30 s, mid 15m/1h/4h bars


class SynthFutures(sf.FakeFutures):
    """Deterministic random walks per (symbol, interval). Like MEXC it includes the forming bar."""

    def __init__(self) -> None:
        super().__init__()
        self.calls: Counter[str] = Counter()
        self.short: set[str] = set()  # symbols with only a short history
        self.stale: set[str] = set()  # symbols whose newest closed bar is missing
        self.broken: set[str] = set()  # symbols whose kline requests fail
        self._cache: dict[tuple[str, str], list[Kline]] = {}

    def _series(self, symbol: str, interval: str) -> list[Kline]:
        key = (symbol, interval)
        if key not in self._cache:
            secs = SECONDS[interval]
            rng = random.Random(f"{symbol}-{interval}")
            price, bars = 100.0, []
            for i in range(int((NOW + timedelta(days=1) - ORIGIN).total_seconds() // secs)):
                op = price
                price = max(price + rng.gauss(0.04 * math.sin(i / 23.0), 0.6), 1.0)
                hi = max(op, price) + abs(rng.gauss(0, 0.3))
                lo = min(op, price) - abs(rng.gauss(0, 0.3))
                bars.append(
                    Kline(
                        open_time=ORIGIN + timedelta(seconds=i * secs),
                        open=op,
                        high=hi,
                        low=lo,
                        close=price,
                        volume=10 + rng.random(),
                        amount=1000.0,
                    )
                )
            self._cache[key] = bars
        return self._cache[key]

    async def klines(
        self, symbol: str, interval: str, start: datetime, end: datetime
    ) -> list[Kline]:
        self.calls[interval] += 1
        if symbol in self.broken:
            raise DataSourceError("mexc_futures", "P1", "klines", "simulated kline failure")
        bars = [b for b in self._series(symbol, interval) if start <= b.open_time <= end]
        if symbol in self.short:
            bars = bars[-150:]
        if symbol in self.stale:
            bars = [
                b
                for b in bars
                if b.open_time + timedelta(seconds=SECONDS[interval]) < end - timedelta(hours=5)
            ]
        return bars


def pick_now() -> datetime:
    """First 5-minute boundary +30 s (from NOW) with an event in the last 3 bars."""
    from tss.agents.signal import SIGNAL_TFS, TIMEFRAMES, Bar, compute_symbol

    fake = SynthFutures()
    series = {
        tf: [
            Bar(k.open_time, k.open, k.high, k.low, k.close, k.volume)
            for k in fake._series("BTC_USDT", TIMEFRAMES[tf][0])
        ]
        for tf in TIMEFRAMES
    }
    for step in range(0, 3000):
        now = NOW + timedelta(minutes=5 * step)
        visible = {
            tf: [b for b in bars if b.open_time + TIMEFRAMES[tf][1] <= now]
            for tf, bars in series.items()
        }
        out = compute_symbol("BTC_USDT", visible, now, {})
        if out.events and all(tf not in out.skipped for tf in SIGNAL_TFS):
            return now
    raise RuntimeError("no event found in the synthetic series")


async def add_selected(c: Any, symbols: list[str], now: datetime) -> None:
    cycle = uuid.uuid4()
    async with c.deps.session_factory() as s:
        for rank, sym in enumerate(symbols, start=1):
            s.add(
                MomentumRanking(
                    cycle_id=cycle,
                    symbol=sym,
                    ts=now,
                    pool_rank=rank,
                    passed_gate2=True,
                    selection_rank=rank,
                    pinned=False,
                )
            )
        await s.commit()


async def scenario_main(cfg: AppConfig, dsn: str) -> None:
    global NOW
    NOW = pick_now()
    print("\n1. Compute, forming bar, caching, idempotency")
    print(f"   (using now = {NOW.isoformat()}, chosen so that events occur in the last 3 bars)")
    fake = SynthFutures()
    c = sf.make_controller(cfg, fake, sf.FakeSpot())
    await c.universe_job()  # BTC / ETH pinned, AAA active
    await add_selected(c, ["AAA_USDT"], NOW)
    agent = SignalAgent(c.deps)

    conn = await asyncpg.connect(dsn)
    events: list[dict[str, Any]] = []
    await conn.add_listener("tss_events", lambda *a: events.append(json.loads(a[3])))
    out = await agent.execute(uuid.uuid4(), NOW)
    await asyncio.sleep(0.3)
    meta = (out.result.meta if out.result else {}) or {}
    check(
        "run SUCCESS with 3 symbols x 3 timeframes = 9 rows",
        out.status == "SUCCESS" and out.result is not None and out.result.rows_out == 9,
        f"{out.status} {meta.get('skipped')}",
    )

    async with c.deps.session_factory() as s:
        rows = list((await s.execute(select(Signal))).scalars())
    check(
        "every row is for a CLOSED bar (bar_close_time <= now): no signal on a forming bar",
        all(r.bar_close_time <= NOW for r in rows) and len(rows) == 9,
    )
    expect = {"5m": timedelta(minutes=5), "15m": timedelta(minutes=15), "1h": timedelta(hours=1)}
    check(
        "bar_close_time is the newest closed boundary per timeframe",
        all(r.bar_close_time == floor_to(NOW, expect[r.timeframe]) for r in rows),
        str(sorted({(r.timeframe, r.bar_close_time.strftime("%H:%M")) for r in rows})),
    )
    check(
        "the in-memory cache never holds a forming bar",
        all(
            b.open_time + d <= NOW
            for (sym, tf), bars in agent._cache._bars.items()
            for b in bars
            for d in [
                {
                    "5m": expect["5m"],
                    "15m": expect["15m"],
                    "1h": expect["1h"],
                    "4h": timedelta(hours=4),
                }[tf]
            ]
        ),
    )
    check(
        "history is 1000 closed bars (4h is limited by the synthetic start date)",
        all(len(agent._cache.get("BTC_USDT", tf)) >= 1000 for tf in ("5m", "15m", "1h"))
        and len(agent._cache.get("BTC_USDT", "4h")) >= 300,
        str({tf: len(agent._cache.get("BTC_USDT", tf)) for tf in ("5m", "15m", "1h", "4h")}),
    )
    check(
        "row values are well formed",
        all(r.m_trend in ("UP", "DOWN") for r in rows),
    )
    sig_events = [e for e in events if e["type"] == "signal_new"]
    check(
        "NOTIFY signal_new sent with the new events",
        len(sig_events) == 1 and len(sig_events[0]["data"]["new_events"]) > 0,
        str(sig_events)[:200],
    )
    async with c.deps.session_factory() as s:
        ev_rows = list((await s.execute(select(SignalEvent))).scalars())
    check(
        "events stored once each, unnotified (notified_at NULL for the P5 phase)",
        len(ev_rows) > 0
        and all(e.notified_at is None for e in ev_rows)
        and len({(e.symbol, e.timeframe, e.bar_close_time, e.event) for e in ev_rows})
        == len(ev_rows),
        f"{len(ev_rows)} events: {sorted({e.event for e in ev_rows})}",
    )
    check("events sit on closed bars only", all(e.bar_close_time <= NOW for e in ev_rows))
    check(
        "BUY/SELL/bullT/bearT events carry the against-4H tag; TD events do not",
        all((e.against_htf is None) == e.event.startswith("TD") for e in ev_rows),
    )

    first_calls = sum(fake.calls.values())
    next_run = NOW + timedelta(minutes=5)  # no new 15m / 1h / 4h bar yet
    fake.calls.clear()
    out2 = await agent.execute(uuid.uuid4(), next_run)
    check(
        "next 5-min run fetches only the 5m series (cache: 3 symbols, 1 request each)",
        dict(fake.calls) == {"Min5": 3},
        f"{dict(fake.calls)} (first run made {first_calls})",
    )
    check(
        "only the timeframe with a new bar is recomputed",
        out2.result is not None and out2.result.rows_out == 3,
        str(out2.result and out2.result.rows_out),
    )

    async with c.deps.session_factory() as s:
        before = (await s.execute(select(func.count()).select_from(Signal))).scalar_one()
        ev_before = (await s.execute(select(func.count()).select_from(SignalEvent))).scalar_one()
    restarted = SignalAgent(c.deps)  # restart: empty cache and no 'already computed' memory
    out3 = await restarted.execute(uuid.uuid4(), next_run)
    async with c.deps.session_factory() as s:
        after = (await s.execute(select(func.count()).select_from(Signal))).scalar_one()
        ev_after = (await s.execute(select(func.count()).select_from(SignalEvent))).scalar_one()
    check(
        "restart re-run is idempotent: no duplicate signal or event rows",
        before == after
        and ev_before == ev_after
        and (out3.result.meta["new_rows"] == 0 if out3.result else False),
        f"signals {before}->{after}, events {ev_before}->{ev_after}",
    )
    check(
        "no NOTIFY when nothing is new", len([e for e in events if e["type"] == "signal_new"]) <= 2
    )
    await conn.close()

    # --- API ---
    code, body = await sf.api_get(cfg, "/api/signals/latest")
    syms = body.get("symbols", [])
    check(
        "/api/signals/latest: pinned symbols first, then selected",
        code == 200 and [s["symbol"] for s in syms] == ["BTC_USDT", "ETH_USDT", "AAA_USDT"],
        str([s["symbol"] for s in syms]),
    )
    groups = {s["symbol"]: s["group"] for s in syms}
    check(
        "BTC/ETH are in the 'majors' group, selected AAA in 'momentum'; configured majors that "
        "are not active contracts (SOL, XRP here) are ignored",
        groups == {"BTC_USDT": "majors", "ETH_USDT": "majors", "AAA_USDT": "momentum"},
        str(groups),
    )
    check(
        "each symbol lists 5m, 15m, 1h rows in order",
        all([r["timeframe"] for r in s["rows"]] == ["5m", "15m", "1h"] for s in syms),
    )
    row = syms[0]["rows"][0]
    needed = {
        "m_trend",
        "last_event",
        "bars_ago",
        "against_htf",
        "zone_position",
        "price_vs_vwap",
        "bar_close_time",
    }
    check("rows carry every Arch §7 output", needed <= set(row), str(needed - set(row)))
    st = await sf.api_status(cfg)
    run = next((r for r in st["runs"] if r["agent"] == "signal"), None)
    check(
        "/api/status shows the signal run and its next run",
        run is not None and st["next_runs"].get("signal") is not None,
    )


async def scenario_failures(cfg: AppConfig) -> None:
    print("\n2. Short history, stale bars, one failing symbol")
    fake = SynthFutures()
    fake.short, fake.stale, fake.broken = {"AAA_USDT"}, {"BBB_USDT"}, {"CCC_USDT"}
    c = sf.make_controller(cfg, fake, sf.FakeSpot())
    await c.universe_job()
    await add_selected(c, ["AAA_USDT", "BBB_USDT", "CCC_USDT"], NOW)
    # BBB / CCC are not contracts in the fake universe; they are selected symbols only
    agent = SignalAgent(c.deps)
    out = await agent.execute(uuid.uuid4(), NOW)
    meta = (out.result.meta if out.result else {}) or {}
    check(
        "one failing symbol gives PARTIAL, others still computed",
        out.status == "PARTIAL"
        and "CCC_USDT" in meta["fetch_failed"]
        and out.result is not None
        and out.result.rows_out == 6,
        f"{out.status} {meta.get('fetch_failed')}",
    )
    skipped = meta["skipped"]
    check(
        "short history is skipped with a reason (nothing invented)",
        any(k.startswith("AAA_USDT") and "insufficient" in v for k, v in skipped.items()),
        str(skipped)[:200],
    )
    check(
        "stale bars are skipped with a reason",
        any(k.startswith("BBB_USDT") and "stale" in v for k, v in skipped.items()),
        str(skipped)[:200],
    )
    async with c.deps.session_factory() as s:
        symbols = {r for (r,) in (await s.execute(select(Signal.symbol).distinct())).all()}
    check("only BTC and ETH have rows", symbols == {"BTC_USDT", "ETH_USDT"}, str(symbols))
    fake.broken = {"BTC_USDT", "ETH_USDT", "AAA_USDT", "BBB_USDT", "CCC_USDT"}
    c.agents["signal"] = SignalAgent(c.deps)
    later = NOW + timedelta(minutes=10)  # the simulated clock, so this is the newest run
    await c.run_agent(c.agents["signal"], uuid.uuid4(), later)
    await c.refresh_state()
    st = await sf.api_status(cfg)
    run = next(r for r in st["runs"] if r["agent"] == "signal")
    check(
        "all symbols failing -> FAILED, naming the component; system degraded, not halted",
        run["status"] == "FAILED"
        and run["error_component"] == "signal"
        and c.halt_reason is None
        and st["state"] != "HALTED",
        f"{run['status']} {st['state']}",
    )


async def scenario_retention(cfg: AppConfig) -> None:
    print("\n3. Retention")
    c = sf.make_controller(cfg, SynthFutures(), sf.FakeSpot())
    now = datetime.now(UTC)
    old = now - timedelta(days=6)
    async with c.deps.session_factory() as s:
        for t, label in ((old, "old"), (now - timedelta(hours=1), "fresh")):
            s.add(
                Signal(
                    symbol="X_USDT",
                    timeframe="5m",
                    bar_close_time=t,
                    m_trend="UP",
                    last_event="NONE",
                    computed_at=t,
                )
            )
            s.add(SignalEvent(symbol="X_USDT", timeframe="5m", bar_close_time=t, event="BUY"))
            _ = label
        await s.commit()
    await c.retention_job()
    async with c.deps.session_factory() as s:
        n_sig = (await s.execute(select(func.count()).select_from(Signal))).scalar_one()
        n_ev = (await s.execute(select(func.count()).select_from(SignalEvent))).scalar_one()
    check(
        "signals and events older than 5 days purged, fresh kept",
        n_sig == 1 and n_ev == 1,
        f"signals={n_sig} events={n_ev}",
    )


async def scenario_pool(cfg: AppConfig) -> None:
    print("\n4. Whole movers pool is evaluated (not only the selection)")
    from tss.realtime.symbols import live_symbols

    c = sf.make_controller(cfg, SynthFutures(), sf.FakeSpot())
    await c.universe_job()
    now = datetime.now(UTC)
    cycle = uuid.uuid4()
    async with c.deps.session_factory() as s:
        for sym, pool_rank, sel, pinned in (
            ("AAA_USDT", 1, 1, False),  # selected
            ("BBB_USDT", 2, None, False),  # pool only: failed the RVOL / change gate
            ("BTC_USDT", 3, None, True),  # pinned context row
        ):
            s.add(
                MomentumRanking(
                    cycle_id=cycle,
                    symbol=sym,
                    ts=now,
                    pool_rank=pool_rank,
                    passed_gate2=sel is not None,
                    selection_rank=sel,
                    pinned=pinned,
                )
            )
        await s.commit()
    got = await live_symbols(c.deps.session_factory, ["ETH_USDT"])
    check_ = sf.check
    check_(
        "selected and pool-only symbols are both evaluated",
        {"AAA_USDT", "BBB_USDT"} <= got,
        str(got),
    )
    check_("pinned context row is not added on its own", "BTC_USDT" not in got, str(got))
    check_("configured major (active contract) is kept", "ETH_USDT" in got, str(got))


async def scenario_setups(cfg: AppConfig) -> None:
    print("\n5. Setup tracker: baseline, new alerts, no repeats, flips")
    c = sf.make_controller(cfg, SynthFutures(), sf.FakeSpot())
    await c.universe_job()
    now = datetime.now(UTC).replace(microsecond=0)
    t0 = floor_to(now, timedelta(minutes=5))
    cycle = uuid.uuid4()
    async with c.deps.session_factory() as ses:
        for rank, sym in enumerate(("AAA_USDT", "BBB_USDT"), start=1):
            ses.add(
                MomentumRanking(
                    cycle_id=cycle,
                    symbol=sym,
                    ts=now,
                    pool_rank=rank,
                    passed_gate2=False,
                    selection_rank=None,  # pool only: evaluated all the same
                    pinned=False,
                )
            )
        await ses.commit()

    async def put(symbol: str, spec: dict[str, tuple[str, str, int | None]]) -> None:
        async with c.deps.session_factory() as ses:
            await ses.execute(Signal.__table__.delete().where(Signal.symbol == symbol))
            for tf, (trend, last, ago) in spec.items():
                ses.add(
                    Signal(
                        symbol=symbol,
                        timeframe=tf,
                        bar_close_time=t0,
                        m_trend=trend,
                        last_event=last,
                        bars_ago=ago,
                        against_htf=False,
                        computed_at=now,
                    )
                )
            await ses.commit()

    long_spec = {
        "5m": ("UP", "BULL_T", 1),
        "15m": ("UP", "NONE", None),
        "1h": ("UP", "BUY", 4),
    }
    short_spec = {
        "5m": ("DOWN", "BEAR_T", 0),
        "15m": ("DOWN", "NONE", None),
        "1h": ("DOWN", "SELL", 2),
    }
    none_spec = {
        "5m": ("DOWN", "NONE", None),
        "15m": ("UP", "NONE", None),
        "1h": ("UP", "NONE", None),
    }
    agent = SetupAgent(c.deps)

    async def state() -> dict[str, SignalSetup]:
        async with c.deps.session_factory() as ses:
            return {r.symbol: r for r in (await ses.execute(select(SignalSetup))).scalars()}

    await put("AAA_USDT", long_spec)
    await put("BBB_USDT", none_spec)
    out = await agent.execute(uuid.uuid4(), now)
    st = await state()
    check(
        "first run is a baseline: the current Long is recorded as notified (no alert burst)",
        out.status == "SUCCESS"
        and set(st) == {"AAA_USDT"}
        and st["AAA_USDT"].bias == "long"
        and st["AAA_USDT"].notified_at is not None
        and out.result is not None
        and out.result.meta["baseline"] is True,
        str(out.result and out.result.meta),
    )
    check(
        "a pool-only symbol (no selection rank) is evaluated; the trigger is the 5m bullT",
        st["AAA_USDT"].trigger_timeframe == "5m" and st["AAA_USDT"].trigger_event == "BULL_T",
    )

    await put("BBB_USDT", short_spec)
    out = await agent.execute(uuid.uuid4(), now)
    st = await state()
    check(
        "a new Short appears: stored unnotified (alert pending), the old Long is not re-alerted",
        st["BBB_USDT"].bias == "short"
        and st["BBB_USDT"].notified_at is None
        and st["AAA_USDT"].notified_at is not None
        and out.result is not None
        and out.result.meta["new"] == 1,
        str(out.result and out.result.meta),
    )
    out = await agent.execute(uuid.uuid4(), now)
    check(
        "same setups on the next run: nothing new",
        out.result is not None and out.result.meta["new"] == 0,
        str(out.result and out.result.meta),
    )

    await put("AAA_USDT", none_spec)
    await agent.execute(uuid.uuid4(), now)
    check("a setup that stops qualifying becomes inactive", not (await state())["AAA_USDT"].active)
    await put("AAA_USDT", long_spec)
    out = await agent.execute(uuid.uuid4(), now)
    st = await state()
    check(
        "it comes back with the very same trigger event: reactivated, NOT alerted again",
        st["AAA_USDT"].active
        and st["AAA_USDT"].notified_at is not None
        and out.result is not None
        and out.result.meta["new"] == 0,
        str(out.result and out.result.meta),
    )
    await put("AAA_USDT", short_spec)
    out = await agent.execute(uuid.uuid4(), now)
    st = await state()
    check(
        "Long flips to Short: a new alert is pending",
        st["AAA_USDT"].bias == "short"
        and st["AAA_USDT"].notified_at is None
        and out.result is not None
        and out.result.meta["new"] == 1,
        str(out.result and out.result.meta),
    )


async def main() -> int:
    cfg = load_config_or_exit()
    base_url = cfg.settings.database_url.get_secret_value()
    sim_url = await sf.make_sim_db(base_url)
    scfg = sf.sim_config(cfg, sim_url)
    dsn = asyncpg_dsn(sim_url)
    try:
        await scenario_main(scfg, dsn)
        await sf.reset_sim_data(scfg)
        await scenario_failures(scfg)
        await sf.reset_sim_data(scfg)
        await scenario_retention(scfg)
        await sf.reset_sim_data(scfg)
        await scenario_pool(scfg)
        await sf.reset_sim_data(scfg)
        await scenario_setups(scfg)
    finally:
        for engine in sf.ENGINES:
            await engine.dispose()
        await sf.drop_sim_db(base_url)
    failed = [r for r in sf.RESULTS if not r[1]]
    print(f"\n{len(sf.RESULTS)} checks, {len(failed)} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
