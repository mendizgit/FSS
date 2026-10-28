"""F9 Signal Agent: FGI Replica V3 on closed 5m / 15m / 1h bars (Arch §7, Phase 4).

Selected + pinned symbols, every 5 minutes. Only CLOSED bars are used (the forming bar is never
fetched into the cache), HTF context comes from the last closed 1h / 4h bars.
"""

from __future__ import annotations

import asyncio
import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, NamedTuple

from tss.agents.base import PARTIAL, SKIPPED, SUCCESS, AgentResult, BaseAgent
from tss.core.errors import DataSourceError
from tss.db.repositories import signals as signals_repo
from tss.indicators.fgi_v3 import (
    Bars,
    FgiParams,
    against_htf,
    build_htf_context,
    compute,
    recent_events,
    snapshot,
    stoch_direction,
)
from tss.realtime.symbols import live_symbols

HISTORY = 1000  # closed bars per timeframe (Arch §7)
CACHE_KEEP = HISTORY + 100
MIN_SIGNAL_BARS = 500  # warm-up for the path-dependent filters
MIN_HTF_BARS = 100
EVENT_LOOKBACK = 3  # bars scanned for events each run (unique key keeps inserts idempotent)
CONCURRENCY = 5

SIGNAL_TFS = ("5m", "15m", "1h")
TIMEFRAMES: dict[str, tuple[str, timedelta]] = {
    "5m": ("Min5", timedelta(minutes=5)),
    "15m": ("Min15", timedelta(minutes=15)),
    "1h": ("Min60", timedelta(hours=1)),
    "4h": ("Hour4", timedelta(hours=4)),
}


class Bar(NamedTuple):
    open_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float | None


def floor_to(dt: datetime, delta: timedelta) -> datetime:
    """Floor to a multiple of `delta` since the Unix epoch (matches MEXC's bar alignment)."""
    seconds = int(delta.total_seconds())
    return datetime.fromtimestamp(int(dt.timestamp()) // seconds * seconds, tz=dt.tzinfo)


def expected_last_open(now: datetime, delta: timedelta) -> datetime:
    """open_time of the newest bar that is closed at `now`."""
    return floor_to(now, delta) - delta


def to_bars(bars: list[Bar]) -> Bars:
    return Bars(
        open_time=[b.open_time for b in bars],
        open=[b.open for b in bars],
        high=[b.high for b in bars],
        low=[b.low for b in bars],
        close=[b.close for b in bars],
        volume=[math.nan if b.volume is None else b.volume for b in bars],
    )


@dataclass
class SymbolOutput:
    rows: list[dict[str, Any]] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    skipped: dict[str, str] = field(default_factory=dict)
    computed: list[tuple[str, datetime]] = field(default_factory=list)  # (tf, bar open_time)


def compute_symbol(
    symbol: str,
    series: dict[str, list[Bar]],
    now: datetime,
    already: dict[str, datetime],
    params: FgiParams | None = None,
) -> SymbolOutput:
    """Pure CPU work for one symbol (runs in a worker thread). Skips timeframes whose newest
    closed bar was already computed, are too short, or are not up to date."""
    out = SymbolOutput()
    one_h, four_h = series.get("1h", []), series.get("4h", [])
    if len(one_h) < MIN_HTF_BARS or len(four_h) < MIN_HTF_BARS:
        for tf in SIGNAL_TFS:
            out.skipped[tf] = f"insufficient_htf_history (1h={len(one_h)}, 4h={len(four_h)})"
        return out
    bars_1h, bars_4h = to_bars(one_h), to_bars(four_h)
    for tf in SIGNAL_TFS:
        delta = TIMEFRAMES[tf][1]
        bars_list = series.get(tf, [])
        if len(bars_list) < MIN_SIGNAL_BARS:
            out.skipped[tf] = f"insufficient_history ({len(bars_list)} < {MIN_SIGNAL_BARS} bars)"
            continue
        newest = bars_list[-1].open_time
        if newest != expected_last_open(now, delta):
            out.skipped[tf] = f"stale_bars (newest closed bar {newest.isoformat()})"
            continue
        if already.get(tf) == newest:
            continue  # nothing new on this timeframe since the last run
        bars = to_bars(bars_list)
        htf = build_htf_context(bars, delta, bars_1h, bars_4h, params)
        result = compute(bars, htf, params)
        snap = snapshot(bars, result, delta, params)
        out.rows.append(
            {
                "symbol": symbol,
                "timeframe": tf,
                "bar_close_time": snap.bar_close_time,
                "m_trend": snap.m_trend,
                "last_event": snap.last_event,
                "bars_ago": snap.bars_ago,
                "against_htf": snap.against_htf,
                "zone_position": snap.zone_position,
                "price_vs_vwap": snap.price_vs_vwap,
                "computed_at": now,
                "htf_dir": snap.htf_dir,
                "long_score": snap.long_score,
                "short_score": snap.short_score,
                "long_factors": snap.long_factors,
                "short_factors": snap.short_factors,
                "entry_long": snap.entry_long,
                "entry_short": snap.entry_short,
                # 5m StochRSI K vs D, the final gate of the 15m entry (5m rows only)
                "stoch_dir": stoch_direction(bars.close, params) if tf == "5m" else None,
            }
        )
        for close_time, event, _ in recent_events(bars, result, delta, EVENT_LOOKBACK):
            idx = bars.open_time.index(close_time - delta)
            out.events.append(
                {
                    "symbol": symbol,
                    "timeframe": tf,
                    "bar_close_time": close_time,
                    "event": event,
                    "against_htf": against_htf(result, idx, event),
                    "notified_at": None,
                }
            )
        out.computed.append((tf, newest))
    return out


class BarCache:
    """Closed bars per (symbol, timeframe), kept in memory between runs."""

    def __init__(self) -> None:
        self._bars: dict[tuple[str, str], list[Bar]] = {}

    def get(self, symbol: str, tf: str) -> list[Bar]:
        return self._bars.get((symbol, tf), [])

    def merge(self, symbol: str, tf: str, fresh: list[Bar]) -> None:
        merged = {b.open_time: b for b in self._bars.get((symbol, tf), [])}
        merged.update({b.open_time: b for b in fresh})
        self._bars[(symbol, tf)] = [merged[t] for t in sorted(merged)][-CACHE_KEEP:]

    def prune(self, keep_symbols: set[str]) -> None:
        for key in [k for k in self._bars if k[0] not in keep_symbols]:
            del self._bars[key]


class SignalAgent(BaseAgent):
    name = "signal"
    critical = False

    def __init__(self, deps: Any) -> None:
        super().__init__(deps)
        self._cache = BarCache()
        self._params = FgiParams(min_other=deps.config.thresholds.signals.min_other_factors)
        self._computed: dict[tuple[str, str], datetime] = {}

    async def _ensure(self, symbol: str, tf: str, now: datetime) -> None:
        interval, delta = TIMEFRAMES[tf]
        cached = self._cache.get(symbol, tf)
        expected = expected_last_open(now, delta)
        if cached and cached[-1].open_time >= expected:
            return
        backfill_from = expected - delta * (HISTORY - 1)
        if cached and expected - cached[-1].open_time < delta * HISTORY:
            start = cached[-1].open_time + delta
        else:
            start = backfill_from
        klines = await self.deps.futures.klines(symbol, interval, start, now)
        fresh = [
            Bar(k.open_time, k.open, k.high, k.low, k.close, k.volume)
            for k in klines
            if k.open_time + delta <= now  # closed bars only: never the forming one
        ]
        self._cache.merge(symbol, tf, fresh)

    async def run(self, cycle_id: uuid.UUID, now: datetime) -> AgentResult:
        majors = self.deps.config.thresholds.signals.majors
        symbols = sorted(await live_symbols(self.deps.session_factory, majors))
        if not symbols:
            return AgentResult(status=SKIPPED, meta={"reason": "no_symbols"})
        self._cache.prune(set(symbols))

        sem = asyncio.Semaphore(CONCURRENCY)
        failed: dict[str, str] = {}

        async def fetch(symbol: str, tf: str) -> None:
            if symbol in failed:
                return
            async with sem:
                try:
                    await self._ensure(symbol, tf, now)
                except DataSourceError as exc:
                    failed.setdefault(symbol, exc.message)

        await asyncio.gather(*(fetch(s, tf) for s in symbols for tf in TIMEFRAMES))
        if len(failed) == len(symbols):
            raise DataSourceError(
                self.name,
                "P4",
                "fetch_klines",
                f"kline requests failed for all {len(symbols)} symbols; "
                f"first: {next(iter(failed.values()))}",
            )

        def work() -> dict[str, SymbolOutput]:
            return {
                s: compute_symbol(
                    s,
                    {tf: self._cache.get(s, tf) for tf in TIMEFRAMES},
                    now,
                    {tf: self._computed[(s, tf)] for tf in SIGNAL_TFS if (s, tf) in self._computed},
                    self._params,
                )
                for s in symbols
                if s not in failed
            }

        outputs = await asyncio.to_thread(work)
        rows = [r for o in outputs.values() for r in o.rows]
        events = [e for o in outputs.values() for e in o.events]
        skipped = {
            f"{s}/{tf}": reason for s, o in outputs.items() for tf, reason in o.skipped.items()
        }
        async with self.deps.session_factory() as session:
            new_rows = await signals_repo.upsert_signals(session, rows)
            new_events = await signals_repo.insert_events(session, events)
            await session.commit()
        for s, o in outputs.items():
            for tf, newest in o.computed:
                self._computed[(s, tf)] = newest

        meta: dict[str, Any] = {
            "symbols": len(symbols),
            "computed": len(rows),
            "new_rows": new_rows,
            "new_events": [[s, tf, ev] for s, tf, _, ev in new_events[:10]],
            "skipped": dict(list(skipped.items())[:20]),
            "fetch_failed": dict(list(failed.items())[:10]),
        }
        return AgentResult(
            status=PARTIAL if failed else SUCCESS,
            rows_in=len(symbols),
            rows_out=len(rows),
            meta=meta,
            event="signal_new" if (new_rows or new_events) else None,
        )
