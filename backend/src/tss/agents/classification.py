"""F4 Derivatives Classification for selected + pinned symbols (Arch §5.5, §6)."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Any

from tss.agents.base import PARTIAL, SUCCESS, AgentResult, BaseAgent
from tss.agents.common import expected_last_closed
from tss.clients.models import SpotKline
from tss.core.errors import DataSourceError
from tss.core.time import floor_to_minutes
from tss.db.models import MarketSnapshot
from tss.db.repositories import contracts as contracts_repo
from tss.db.repositories import discovery as discovery_repo
from tss.db.repositories import market as market_repo
from tss.domain.calculations import (
    has_gap,
    is_closed,
    nearest_within,
    pct_change,
    window_price_change,
    window_sum_change,
)
from tss.domain.classification import (
    ClassificationResult,
    Reliability,
    WindowMetrics,
    classify,
    with_tf_conflict,
)

BARS_PER_WINDOW = {"1h": 4, "4h": 16}
WINDOW = {"1h": timedelta(hours=1), "4h": timedelta(hours=4)}
SPOT_KLINE_LIMIT = 40  # >= 2 x 16 closed bars + the forming bar
CONCURRENCY = 5


class ClassificationAgent(BaseAgent):
    name = "classification"
    critical = True

    async def _spot_klines(
        self, spot_symbols: dict[str, str], now: datetime
    ) -> tuple[dict[str, list[SpotKline]], int]:
        out: dict[str, list[SpotKline]] = {}
        failed = 0
        sem = asyncio.Semaphore(CONCURRENCY)

        async def fetch(symbol: str, spot_symbol: str) -> None:
            nonlocal failed
            async with sem:
                try:
                    bars = await self.deps.spot.klines_15m(spot_symbol, SPOT_KLINE_LIMIT)
                except DataSourceError:
                    failed += 1
                    return
            out[symbol] = [b for b in bars if is_closed(b.open_time, now)]

        await asyncio.gather(*(fetch(s, sp) for s, sp in spot_symbols.items()))
        return out, failed

    async def run(self, cycle_id: uuid.UUID, now: datetime) -> AgentResult:
        ccfg = self.deps.config.thresholds.classification
        tol = ccfg.snapshot_match_tolerance_s
        ts = floor_to_minutes(now, 15)
        expected = expected_last_closed(now)
        windows = list(ccfg.windows)
        max_w = max(WINDOW[w] for w in windows)

        async with self.deps.session_factory() as session:
            contracts = {c.symbol: c for c in await contracts_repo.active_contracts(session)}
            selected = await discovery_repo.selected_symbols(session, cycle_id)
            symbols = sorted(set(selected) | {s for s, c in contracts.items() if c.pinned})
            newest = await market_repo.latest_snapshots(session, symbols)
            history = await market_repo.snapshot_history(
                session, symbols, now - max_w - timedelta(minutes=30)
            )
            earliest = await market_repo.earliest_snapshot_ts(session, symbols)
            bars = await market_repo.last_klines(
                session, symbols, 2 * max(BARS_PER_WINDOW.values())
            )

        spot_map = {s: contracts[s].spot_symbol for s in symbols if contracts[s].spot_symbol}
        spot_bars, spot_failed = await self._spot_klines(
            {s: sp for s, sp in spot_map.items() if sp}, now
        )

        records: list[dict[str, Any]] = []
        for symbol in symbols:
            snap: MarketSnapshot | None = newest.get(symbol)
            series = bars.get(symbol, [])
            closes = [b.close for b in series]
            amounts = [b.amount for b in series]
            times = [b.open_time for b in series]
            spot_series = spot_bars.get(symbol)
            spot_ok = bool(spot_series) and spot_series[-1].open_time == expected  # type: ignore[index]
            spot_quote = [b.quote_volume for b in spot_series] if spot_series and spot_ok else []
            hist = [(h.ts, h) for h in history.get(symbol, [])]
            results: dict[str, ClassificationResult] = {}
            metrics_by_window: dict[str, WindowMetrics] = {}
            for w in windows:
                n = BARS_PER_WINDOW[w]
                then: MarketSnapshot | None = None
                if snap is not None:
                    then = nearest_within(hist, snap.ts - WINDOW[w], tol)
                first = earliest.get(symbol)
                covers = (
                    snap is not None
                    and first is not None
                    and first <= snap.ts - WINDOW[w] + timedelta(seconds=tol)
                )
                funding_now = snap.funding_rate if snap else None
                funding_then = then.funding_rate if then else None
                metrics = WindowMetrics(
                    price_change_pct=window_price_change(closes, n),
                    oi_change_pct=pct_change(snap.hold_vol, then.hold_vol)
                    if snap and then
                    else None,
                    fut_volume_change_pct=window_sum_change(amounts, n),
                    spot_volume_change_pct=window_sum_change(spot_quote, n) if spot_quote else None,
                    funding_now=funding_now,
                    funding_delta=(
                        funding_now - funding_then
                        if funding_now is not None and funding_then is not None
                        else None
                    ),
                )
                reliability = Reliability(
                    snapshot_stale=snap is None
                    or (now - snap.ts).total_seconds() > ccfg.stale_after_s,
                    liquid=bool(snap and snap.liquid),
                    kline_gap=not times or has_gap(times, 2 * n) or times[-1] != expected,
                    oi_history_covers_window=covers,
                )
                metrics_by_window[w] = metrics
                results[w] = classify(metrics, reliability, ccfg)
            results = with_tf_conflict(results)
            for w in windows:
                m, r = metrics_by_window[w], results[w]
                records.append(
                    {
                        "cycle_id": cycle_id,
                        "symbol": symbol,
                        "window": w,
                        "ts": ts,
                        "price_change_pct": m.price_change_pct,
                        "oi_change_pct": m.oi_change_pct,
                        "fut_volume_change_pct": m.fut_volume_change_pct,
                        "spot_volume_change_pct": m.spot_volume_change_pct,
                        "funding_now": m.funding_now,
                        "funding_delta": m.funding_delta,
                        "state": r.state,
                        "flags": r.flags,
                        "unreliable_reasons": r.unreliable_reasons,
                    }
                )
        async with self.deps.session_factory() as session:
            await discovery_repo.save_classifications(session, records)
            await session.commit()
        unreliable = sum(1 for r in records if r["state"] == "UNRELIABLE")
        return AgentResult(
            status=PARTIAL if spot_failed else SUCCESS,
            rows_in=len(symbols),
            rows_out=len(records),
            selected_count=len(selected),
            meta={"unreliable": unreliable, "spot_failed": spot_failed},
        )
