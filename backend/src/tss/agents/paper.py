"""F13 Paper trader: dummy-money test of the 15m entry alerts (analysis only, no real orders).

Runs after the Setup agent. Order of work each run:
1. open trades: scan closed 5m bars since entry for the stop / target; else close on timeout
   (no early close when the signal turns invalid).
2. new alerts (active setup, not yet notified, recent) open one trade each at the last closed 5m
   close, if free margin is left. A setup opens at most one trade (unique symbol, side, time).
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Any

from tss.agents.base import PARTIAL, SKIPPED, SUCCESS, AgentResult, BaseAgent
from tss.core.errors import DataSourceError
from tss.db.models.paper import PaperTrade
from tss.db.models.signals import SignalSetup
from tss.db.repositories import paper as paper_repo
from tss.db.repositories import signals as signals_repo
from tss.domain import paper as pm
from tss.domain.notifier import SETUP_MAX_AGE

BAR = timedelta(minutes=5)
CONCURRENCY = 5


class PaperAgent(BaseAgent):
    name = "paper"
    critical = False

    async def _bars(self, symbol: str, start: datetime, now: datetime) -> list[pm.Bar5]:
        klines = await self.deps.futures.klines(symbol, "Min5", start, now)
        bars = [
            pm.Bar5(k.open_time, k.open_time + BAR, k.high, k.low, k.close)
            for k in klines
            if k.open_time + BAR <= now  # closed bars only
        ]
        return sorted(bars, key=lambda b: b.open_time)

    async def run(self, cycle_id: uuid.UUID, now: datetime) -> AgentResult:
        cfg = self.deps.config.thresholds.paper
        if not cfg.enabled:
            return AgentResult(status=SKIPPED, meta={"reason": "disabled"})
        majors = self.deps.config.thresholds.signals.majors
        failed: dict[str, str] = {}
        sem = asyncio.Semaphore(CONCURRENCY)

        async def fetch(symbol: str, start: datetime) -> tuple[str, list[pm.Bar5]]:
            async with sem:
                try:
                    return symbol, await self._bars(symbol, start, now)
                except DataSourceError as exc:
                    failed[symbol] = exc.message
                    return symbol, []

        async with self.deps.session_factory() as session:
            opened = await paper_repo.open_trades(session)
            setups = await signals_repo.get_setups(session)
            fresh = [
                s
                for s in setups.values()
                if s.active
                and s.notified_at is None
                and now - s.detected_at <= SETUP_MAX_AGE
                and s.symbol not in majors
            ]
            known = await paper_repo.known_setups(
                session, {(s.symbol, s.bias, s.detected_at) for s in fresh}
            )
            fresh = [s for s in fresh if (s.symbol, s.bias, s.detected_at) not in known]
            # an alert raised while a trade on the symbol was open never opens a trade, even
            # after that trade has closed
            blocked = await paper_repo.blocked_setups(
                session, {(s.symbol, s.bias, s.detected_at) for s in fresh}
            )
            fresh = [s for s in fresh if (s.symbol, s.bias, s.detected_at) not in blocked]
            holding = {t.symbol for t in opened}

            # 1) open trades
            starts = {
                t.symbol: min(x.opened_at for x in opened if x.symbol == t.symbol) for t in opened
            }
            fetched = dict(await asyncio.gather(*(fetch(sym, st) for sym, st in starts.items())))
            closed = 0
            for t in opened:
                bars = [b for b in fetched.get(t.symbol, []) if b.open_time >= t.opened_at]
                if not bars:
                    continue
                if self._close_if_done(t, bars, now):
                    closed += 1
                    holding.discard(t.symbol)
            await session.flush()

            # 2) new alerts
            balance = cfg.start_balance_usdt + await paper_repo.closed_pnl(session)
            used = sum(t.margin_usdt for t in opened if t.status == "open")
            new = 0
            skipped = 0
            entry_bars = dict(
                await asyncio.gather(*(fetch(s.symbol, now - timedelta(minutes=20)) for s in fresh))
            )
            views = await signals_repo.load_views(session, [s.symbol for s in fresh])
            for s in sorted(fresh, key=lambda x: (x.detected_at, x.symbol)):
                bars = entry_bars.get(s.symbol, [])
                if not bars or s.symbol in holding:
                    skipped += 1
                    continue
                if balance - used < cfg.margin_per_trade_usdt:
                    skipped += 1
                    self.log.warning(
                        "paper trade skipped: no free margin",
                        symbol=s.symbol,
                        free=round(balance - used, 2),
                    )
                    continue
                row = self._new_row(s, bars[-1], views.get(s.symbol, []), now)
                if await paper_repo.insert_trade(session, row):
                    used += cfg.margin_per_trade_usdt
                    holding.add(s.symbol)
                    new += 1
            await session.commit()

        meta: dict[str, Any] = {
            "open": len(holding),
            "opened": new,
            "closed": closed,
            "skipped": skipped,
            "failed": len(failed),
        }
        status = PARTIAL if failed else SUCCESS
        return AgentResult(
            status=status, rows_in=len(opened) + len(fresh), rows_out=new + closed, meta=meta
        )

    def _close_if_done(
        self,
        t: PaperTrade,
        bars: list[pm.Bar5],
        now: datetime,
    ) -> bool:
        cfg = self.deps.config.thresholds.paper
        lv = pm.Levels(
            t.entry_price,
            t.stop_price,
            t.target_price,
            t.notional_usdt,
            t.notional_usdt / t.entry_price,
        )
        done = pm.scan(t.side, lv, bars, cfg.slippage_pct)
        if done is None and now - t.opened_at >= timedelta(minutes=cfg.timeout_minutes):
            done = pm.market_exit(t.side, "timeout", bars, lv, cfg.slippage_pct)
        if done is None:
            t.mfe_pct, t.mae_pct = pm.excursions(t.side, t.entry_price, bars)
            t.updated_at = now
            return False
        res = pm.settle(t.side, lv, done.price, cfg.stop_pct, cfg.fee_pct)
        t.status = "closed"
        t.closed_at = done.time
        t.exit_price = done.price
        t.exit_reason = done.reason
        t.mfe_pct, t.mae_pct = done.mfe_pct, done.mae_pct
        t.fees_usdt, t.pnl_usdt, t.r_multiple = res.fees, res.pnl, res.r_multiple
        t.updated_at = now
        return True

    def _new_row(
        self, s: SignalSetup, bar: pm.Bar5, views: list[Any], now: datetime
    ) -> dict[str, Any]:
        cfg = self.deps.config.thresholds.paper
        lv = pm.levels(
            s.bias,
            bar.close,
            cfg.margin_per_trade_usdt,
            cfg.leverage,
            cfg.stop_pct,
            cfg.reward_risk,
            cfg.slippage_pct,
        )
        view15 = next((v for v in views if v.timeframe == "15m"), None)
        events = [(e.event, e.bars_ago) for e in view15.events] if view15 else []
        text, confirms = pm.flip_tags(s.bias, events)
        return {
            "symbol": s.symbol,
            "side": s.bias,
            "status": "open",
            "setup_detected_at": s.detected_at,
            "opened_at": bar.close_time,
            "entry_price": lv.entry,
            "stop_price": lv.stop,
            "target_price": lv.target,
            "margin_usdt": cfg.margin_per_trade_usdt,
            "notional_usdt": lv.notional,
            "score": s.score,
            "factors": s.factors,
            "against_htf": s.against_htf,
            "flip_events": text,
            "flip_confirms": confirms,
            "mfe_pct": 0.0,
            "mae_pct": 0.0,
            "updated_at": now,
        }
