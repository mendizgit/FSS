"""GET /api/paper: dummy-money results of the 15m entry alerts (analysis only)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from tss.api.deps import get_config, get_session
from tss.api.schemas.models import PaperGroupOut, PaperOut, PaperSummaryOut, PaperTradeOut
from tss.core.settings import AppConfig
from tss.db.models.fgi_paper import FgiPaperTrade
from tss.db.models.paper import PaperTrade
from tss.db.repositories import fgi_paper as fgi_repo
from tss.db.repositories import market as market_repo
from tss.db.repositories import paper as paper_repo

router = APIRouter()
CLOSED_LIMIT = 100


def unrealized(t: PaperTrade, price: float | None) -> float | None:
    if price is None:
        return None
    sign = 1 if t.side == "long" else -1
    return (price - t.entry_price) * (t.notional_usdt / t.entry_price) * sign


def trade_out(t: PaperTrade, price: float | None = None) -> PaperTradeOut:
    return PaperTradeOut(
        id=t.id,
        symbol=t.symbol,
        side=t.side,
        status=t.status,
        opened_at=t.opened_at,
        entry_price=t.entry_price,
        stop_price=t.stop_price,
        target_price=t.target_price,
        score=t.score,
        factors=t.factors,
        against_htf=t.against_htf,
        flip_events=t.flip_events,
        flip_confirms=t.flip_confirms,
        mfe_pct=t.mfe_pct,
        mae_pct=t.mae_pct,
        last_price=price,
        unrealized_usdt=unrealized(t, price) if t.status == "open" else None,
        closed_at=t.closed_at,
        exit_price=t.exit_price,
        exit_reason=t.exit_reason,
        pnl_usdt=t.pnl_usdt,
        r_multiple=t.r_multiple,
    )


def group(trades: list[PaperTrade], key: Callable[[PaperTrade], str]) -> list[PaperGroupOut]:
    buckets: dict[str, list[PaperTrade]] = {}
    for t in trades:
        buckets.setdefault(key(t), []).append(t)
    out = []
    for k in sorted(buckets):
        ts = buckets[k]
        out.append(
            PaperGroupOut(
                key=k,
                trades=len(ts),
                wins=sum(1 for t in ts if (t.pnl_usdt or 0) > 0),
                pnl_usdt=sum(t.pnl_usdt or 0 for t in ts),
                avg_r=sum(t.r_multiple or 0 for t in ts) / len(ts),
            )
        )
    return out


def max_drawdown(closed: list[PaperTrade]) -> float:
    peak = equity = worst = 0.0
    for t in sorted(closed, key=lambda x: x.closed_at or x.opened_at):
        equity += t.pnl_usdt or 0
        peak = max(peak, equity)
        worst = max(worst, peak - equity)
    return worst


@router.get("/paper", response_model=PaperOut)
async def paper(
    session: Annotated[AsyncSession, Depends(get_session)],
    cfg: Annotated[AppConfig, Depends(get_config)],
) -> PaperOut:
    pc = cfg.thresholds.paper
    opened = await paper_repo.open_trades(session)
    closed = await paper_repo.all_closed(session)
    snaps = await market_repo.latest_snapshots(session, {t.symbol for t in opened})
    prices = {s: snap.last_price for s, snap in snaps.items()}
    realized = sum(t.pnl_usdt or 0 for t in closed)
    open_out = [trade_out(t, prices.get(t.symbol)) for t in opened]
    wins = [t for t in closed if (t.pnl_usdt or 0) > 0]
    gain = sum(t.pnl_usdt or 0 for t in wins)
    loss = -sum(t.pnl_usdt or 0 for t in closed if (t.pnl_usdt or 0) < 0)
    n = len(closed)
    summary = PaperSummaryOut(
        start_balance_usdt=pc.start_balance_usdt,
        balance_usdt=pc.start_balance_usdt + realized,
        realized_usdt=realized,
        unrealized_usdt=sum(o.unrealized_usdt or 0 for o in open_out),
        margin_in_use_usdt=sum(t.margin_usdt for t in opened),
        open_trades=len(opened),
        closed_trades=n,
        wins=len(wins),
        win_rate_pct=len(wins) / n * 100 if n else None,
        avg_r=sum(t.r_multiple or 0 for t in closed) / n if n else None,
        profit_factor=gain / loss if loss > 0 else None,
        max_drawdown_usdt=max_drawdown(closed),
        leverage=pc.leverage,
        margin_per_trade_usdt=pc.margin_per_trade_usdt,
        stop_pct=pc.stop_pct,
        reward_risk=pc.reward_risk,
        timeout_minutes=pc.timeout_minutes,
    )
    recent = sorted(closed, key=lambda t: t.closed_at or t.opened_at, reverse=True)[:CLOSED_LIMIT]
    return PaperOut(
        summary=summary,
        open=open_out,
        closed=[trade_out(t) for t in recent],
        by_score=group(closed, lambda t: f"{t.score}/5"),
        by_flip_confirm=group(closed, lambda t: "flip confirms" if t.flip_confirms else "no flip"),
        by_htf=group(
            closed,
            lambda t: (
                "4H with" if t.against_htf is False else "4H against" if t.against_htf else "4H n/a"
            ),
        ),
        by_exit=group(closed, lambda t: t.exit_reason or "?"),
        by_side=group(closed, lambda t: t.side),
    )


def fgi_unrealized(t: FgiPaperTrade, price: float | None) -> float | None:
    """Closed legs net of their fees plus the open remainder at the latest price."""
    if price is None:
        return None
    sign = 1 if t.side == "long" else -1
    return t.gross_usdt - t.fees_usdt + (price - t.entry_price) * t.qty * t.remaining_frac * sign


def fgi_trade_out(t: FgiPaperTrade, price: float | None = None) -> PaperTradeOut:
    stage = "BE" if t.be else "TP1" if t.tp1_done else ""
    return PaperTradeOut(
        id=t.id,
        symbol=t.symbol,
        side=t.side,
        status=t.status,
        opened_at=t.opened_at,
        entry_price=t.entry_price,
        stop_price=t.stop_price,
        target_price=t.tp2_price,
        score=t.score,
        factors=f"ADX {t.adx:.0f} TP1 {t.tp1_price:g}" + (f" {stage}" if stage else ""),
        against_htf=None,
        flip_events=None,
        flip_confirms=False,
        mfe_pct=t.mfe_pct,
        mae_pct=t.mae_pct,
        last_price=price,
        unrealized_usdt=fgi_unrealized(t, price) if t.status == "open" else None,
        closed_at=t.closed_at,
        exit_price=t.exit_price,
        exit_reason=t.exit_reason,
        pnl_usdt=t.pnl_usdt,
        r_multiple=t.r_multiple,
    )


def fgi_group(
    trades: list[FgiPaperTrade], key: Callable[[FgiPaperTrade], str]
) -> list[PaperGroupOut]:
    buckets: dict[str, list[FgiPaperTrade]] = {}
    for t in trades:
        buckets.setdefault(key(t), []).append(t)
    return [
        PaperGroupOut(
            key=k,
            trades=len(ts),
            wins=sum(1 for t in ts if (t.pnl_usdt or 0) > 0),
            pnl_usdt=sum(t.pnl_usdt or 0 for t in ts),
            avg_r=sum(t.r_multiple or 0 for t in ts) / len(ts),
        )
        for k, ts in sorted(buckets.items())
    ]


@router.get("/paper-fgi", response_model=PaperOut)
async def paper_fgi(
    session: Annotated[AsyncSession, Depends(get_session)],
    cfg: Annotated[AppConfig, Depends(get_config)],
) -> PaperOut:
    """Same shape as /paper, for the FGI Pro strategy test (partial exits, no fixed timeout)."""
    pc = cfg.thresholds.paper_fgi
    opened = await fgi_repo.open_trades(session)
    closed = await fgi_repo.all_closed(session)
    snaps = await market_repo.latest_snapshots(session, {t.symbol for t in opened})
    prices = {s: snap.last_price for s, snap in snaps.items()}
    realized = sum(t.pnl_usdt or 0 for t in closed)
    open_out = [fgi_trade_out(t, prices.get(t.symbol)) for t in opened]
    wins = [t for t in closed if (t.pnl_usdt or 0) > 0]
    gain = sum(t.pnl_usdt or 0 for t in wins)
    loss = -sum(t.pnl_usdt or 0 for t in closed if (t.pnl_usdt or 0) < 0)
    n = len(closed)
    ordered = sorted(closed, key=lambda x: x.closed_at or x.opened_at)
    peak = equity = worst = 0.0
    for t in ordered:
        equity += t.pnl_usdt or 0
        peak = max(peak, equity)
        worst = max(worst, peak - equity)
    summary = PaperSummaryOut(
        start_balance_usdt=pc.start_balance_usdt,
        balance_usdt=pc.start_balance_usdt + realized,
        realized_usdt=realized,
        unrealized_usdt=sum(o.unrealized_usdt or 0 for o in open_out),
        margin_in_use_usdt=sum(t.margin_usdt for t in opened),
        open_trades=len(opened),
        closed_trades=n,
        wins=len(wins),
        win_rate_pct=len(wins) / n * 100 if n else None,
        avg_r=sum(t.r_multiple or 0 for t in closed) / n if n else None,
        profit_factor=gain / loss if loss > 0 else None,
        max_drawdown_usdt=worst,
        leverage=pc.leverage,
        margin_per_trade_usdt=pc.margin_per_trade_usdt,
        stop_pct=pc.stop_cap_pct,
        reward_risk=0.0,
        timeout_minutes=0,
    )
    return PaperOut(
        summary=summary,
        open=open_out,
        closed=[fgi_trade_out(t) for t in reversed(ordered)][:CLOSED_LIMIT],
        by_score=fgi_group(closed, lambda t: f"{t.score}/6"),
        by_flip_confirm=[],
        by_htf=[],
        by_exit=fgi_group(closed, lambda t: t.exit_reason or "?"),
        by_side=fgi_group(closed, lambda t: t.side),
    )
