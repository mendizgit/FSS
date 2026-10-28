"""F14 FGI paper trader: dummy-money forward test of the FGI Pro strategy (analysis only).

Runs every 15 minutes after the bar close. Pool: the top `pool_size` active USDT perpetuals by
24h turnover (denylist applied). Order of work each run:
1. open trades: apply the closed 5m bars since the last run (stop, TP1 partial, TP2, break-even,
   next-open exit after a closed 15m bar shows the 1H trend against the trade).
2. new entries: a signal on the newest closed 15m bar opens one trade at the last closed 5m
   close, if the symbol is free, fewer than `max_open` trades are open and margin is left.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Any, NamedTuple

from tss.agents.base import PARTIAL, SKIPPED, SUCCESS, AgentResult, BaseAgent
from tss.core.errors import DataSourceError
from tss.core.settings import FgiPaperCfg
from tss.core.time import floor_to_minutes
from tss.db.models.fgi_paper import FgiPaperTrade
from tss.db.repositories import contracts as contracts_repo
from tss.db.repositories import fgi_paper as repo
from tss.db.repositories import market as market_repo
from tss.domain import fgi_paper as fm
from tss.indicators import fgi_strategy as strat

BAR5 = timedelta(minutes=5)
CONCURRENCY = 5
HISTORY = {"Min15": 320, "Min60": 250, "Hour4": 130}  # closed bars read per timeframe
MAX_SIGNAL_AGE = timedelta(minutes=20)  # a signal older than this (missed run) is not entered


class SymbolData(NamedTuple):
    b15: list[strat.Bar]
    b1h: list[strat.Bar]
    b4h: list[strat.Bar]


class FgiPaperAgent(BaseAgent):
    name = "fgi_paper"
    critical = False

    async def _bars(
        self, symbol: str, interval: str, step: timedelta, start: datetime, now: datetime
    ) -> list[strat.Bar]:
        klines = await self.deps.futures.klines(symbol, interval, start, now)
        bars = [
            strat.Bar(k.open_time, k.open, k.high, k.low, k.close)
            for k in klines
            if k.open_time + step <= now  # closed bars only
        ]
        return sorted(bars, key=lambda b: b.open_time)

    async def _pool(self, cfg: FgiPaperCfg) -> list[str]:
        quote = self.deps.config.thresholds.universe.quote_asset
        async with self.deps.session_factory() as session:
            contracts = [
                c for c in await contracts_repo.active_contracts(session) if c.quote_coin == quote
            ]
            snaps = await market_repo.latest_snapshots(session, [c.symbol for c in contracts])
        ranked = sorted(
            (s for s in snaps.values() if s.fut_amount24 is not None),
            key=lambda s: s.fut_amount24 or 0.0,
            reverse=True,
        )
        return [s.symbol for s in ranked[: cfg.pool_size]]

    async def run(self, cycle_id: uuid.UUID, now: datetime) -> AgentResult:
        cfg = self.deps.config.thresholds.paper_fgi
        if not cfg.enabled:
            return AgentResult(status=SKIPPED, meta={"reason": "disabled"})
        params = strat.StrategyParams(
            min_score=cfg.min_score, adx_min=cfg.adx_min, use_4h=cfg.use_4h
        )
        failed: dict[str, str] = {}
        sem = asyncio.Semaphore(CONCURRENCY)
        pool = await self._pool(cfg)

        async def load(symbol: str) -> tuple[str, SymbolData | None]:
            async with sem:
                try:
                    b15 = await self._bars(
                        symbol, "Min15", strat.BAR_15M, now - HISTORY["Min15"] * strat.BAR_15M, now
                    )
                    b1h = await self._bars(
                        symbol, "Min60", strat.BAR_1H, now - HISTORY["Min60"] * strat.BAR_1H, now
                    )
                    b4h = await self._bars(
                        symbol, "Hour4", strat.BAR_4H, now - HISTORY["Hour4"] * strat.BAR_4H, now
                    )
                except DataSourceError as exc:
                    failed[symbol] = exc.message
                    return symbol, None
                return symbol, SymbolData(b15, b1h, b4h)

        async def fetch5(symbol: str, start: datetime) -> tuple[str, list[fm.Bar5]]:
            async with sem:
                try:
                    bars = await self._bars(symbol, "Min5", BAR5, start, now)
                except DataSourceError as exc:
                    failed[symbol] = exc.message
                    return symbol, []
                return symbol, [fm.Bar5(b.open_time, b.open_time + BAR5, *b[1:]) for b in bars]

        async with self.deps.session_factory() as session:
            opened = await repo.open_trades(session)
            holding = {t.symbol for t in opened}
            wanted = sorted(set(pool) | holding)
            data = {s: d for s, d in await asyncio.gather(*(load(s) for s in wanted)) if d}
            series = {
                s: strat.compute(d.b15, d.b1h, d.b4h, params)
                if len(d.b15) >= strat.MIN_BARS_15M
                and len(d.b1h) >= strat.MIN_BARS_HTF
                and len(d.b4h) >= strat.MIN_BARS_HTF
                else []
                for s, d in data.items()
            }

            # 1) open trades
            fetched = dict(
                await asyncio.gather(*(fetch5(t.symbol, t.opened_at - BAR5) for t in opened))
            )
            closed = 0
            for t in opened:
                if self._advance(t, fetched.get(t.symbol, []), data.get(t.symbol), series, now):
                    closed += 1
                    holding.discard(t.symbol)
            await session.flush()

            # 2) new entries on the newest closed 15m bar
            bar_close = floor_to_minutes(now, 15)
            candidates: list[tuple[str, str, strat.Signal]] = []
            for symbol in pool:
                sigs = series.get(symbol)
                sig = sigs[-1] if sigs else None
                if (
                    sig is None
                    or symbol in holding
                    or sig.close_time != bar_close
                    or now - sig.close_time > MAX_SIGNAL_AGE
                ):
                    continue
                if sig.long != sig.short:
                    candidates.append((symbol, "long" if sig.long else "short", sig))
            entry_bars = dict(
                await asyncio.gather(
                    *(fetch5(sym, now - timedelta(minutes=20)) for sym, _, _ in candidates)
                )
            )
            balance = cfg.start_balance_usdt + await repo.closed_pnl(session)
            used = len(holding) * cfg.margin_per_trade_usdt
            new = skipped = 0
            for symbol, side, sig in sorted(candidates, key=lambda c: (-c[2].adx, c[0])):
                bars5 = entry_bars.get(symbol, [])
                if not bars5:
                    skipped += 1
                    continue
                if len(holding) >= cfg.max_open or balance - used < cfg.margin_per_trade_usdt:
                    skipped += 1
                    continue
                row = self._new_row(symbol, side, sig, bars5[-1], cfg, now)
                if row is not None and await repo.insert_trade(session, row):
                    used += cfg.margin_per_trade_usdt
                    holding.add(symbol)
                    new += 1
            await session.commit()

        meta: dict[str, Any] = {
            "pool": len(pool),
            "open": len(holding),
            "opened": new,
            "closed": closed,
            "skipped": skipped,
            "failed": len(failed),
        }
        return AgentResult(
            status=PARTIAL if failed else SUCCESS,
            rows_in=len(opened) + len(candidates),
            rows_out=new + closed,
            meta=meta,
        )

    def _advance(
        self,
        t: FgiPaperTrade,
        bars5: list[fm.Bar5],
        data: SymbolData | None,
        series: dict[str, list[strat.Signal | None]],
        now: datetime,
    ) -> bool:
        """Apply new closed 5m bars to the trade; True when it is now closed."""
        cfg = self.deps.config.thresholds.paper_fgi
        boundaries: dict[datetime, fm.Boundary] = {}
        if data is not None:
            sigs = series.get(t.symbol, [])
            offset = len(data.b15) - len(sigs) if sigs else 0
            for i, bar in enumerate(data.b15):
                sig = sigs[i - offset] if sigs and i >= offset else None
                boundaries[bar.open_time + strat.BAR_15M] = fm.Boundary(
                    bar.high,
                    bar.low,
                    sig.atr if sig else t.atr,
                    bool(sig and sig.trend_bull),
                    bool(sig and sig.trend_bear),
                )
        st = fm.State(
            side=t.side,
            entry=t.entry_price,
            stop=t.stop_price,
            stop0=t.stop0_price,
            tp1=t.tp1_price,
            tp2=t.tp2_price,
            qty=t.qty,
            remaining=t.remaining_frac,
            tp1_done=t.tp1_done,
            be=t.be,
            flip_pending=t.flip_pending,
            gross=t.gross_usdt,
            fees=t.fees_usdt,
        )
        new_bars = [b for b in bars5 if b.close_time > t.scanned_to]
        done = fm.advance(
            st,
            new_bars,
            boundaries,
            tp1_fraction=cfg.tp1_fraction,
            slippage_pct=cfg.slippage_pct,
            fee_pct=cfg.fee_pct,
        )
        t.stop_price, t.remaining_frac = st.stop, st.remaining
        t.tp1_done, t.be, t.flip_pending = st.tp1_done, st.be, st.flip_pending
        t.gross_usdt, t.fees_usdt = st.gross, st.fees
        if new_bars:
            t.scanned_to = new_bars[-1].close_time
        seen = [b for b in bars5 if b.close_time <= t.scanned_to]
        t.mfe_pct, t.mae_pct = fm.excursions(t.side, t.entry_price, seen)
        t.updated_at = now
        if done is None:
            return False
        res = fm.settle(st)
        t.status = "closed"
        t.closed_at = done.time
        t.exit_price = done.price
        t.exit_reason = done.reason
        t.fees_usdt, t.pnl_usdt, t.r_multiple = res.fees, res.pnl, res.r_multiple
        return True

    def _new_row(
        self,
        symbol: str,
        side: str,
        sig: strat.Signal,
        bar: fm.Bar5,
        cfg: FgiPaperCfg,
        now: datetime,
    ) -> dict[str, Any] | None:
        long = side == "long"
        plan = fm.plan(
            side,
            sig.close,
            sig.atr,
            sig.long_stop if long else sig.short_stop,
            bar.close,
            margin=cfg.margin_per_trade_usdt,
            leverage=cfg.leverage,
            stop_cap_pct=cfg.stop_cap_pct,
            tp1_atr=cfg.tp1_atr,
            tp2_atr=cfg.tp2_atr,
            slippage_pct=cfg.slippage_pct,
        )
        if plan is None:
            return None
        return {
            "symbol": symbol,
            "side": side,
            "status": "open",
            "signal_at": sig.close_time,
            "opened_at": bar.close_time,
            "entry_price": plan.entry,
            "stop_price": plan.stop,
            "stop0_price": plan.stop,
            "tp1_price": plan.tp1,
            "tp2_price": plan.tp2,
            "atr": sig.atr,
            "qty": plan.qty,
            "margin_usdt": cfg.margin_per_trade_usdt,
            "notional_usdt": plan.notional,
            "score": sig.long_score if long else sig.short_score,
            "adx": sig.adx,
            "remaining_frac": 1.0,
            "tp1_done": False,
            "be": False,
            "flip_pending": False,
            "gross_usdt": 0.0,
            "fees_usdt": 0.0,
            "scanned_to": bar.close_time,
            "mfe_pct": 0.0,
            "mae_pct": 0.0,
            "updated_at": now,
        }
