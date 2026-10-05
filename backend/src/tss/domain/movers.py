"""UTC-day gainers / losers (Arch §5.6). Pure functions."""

from __future__ import annotations

from dataclasses import dataclass

from tss.domain.calculations import pct_change


@dataclass(frozen=True)
class MoverInput:
    symbol: str
    last_price: float | None
    day_open: float | None
    fut_amount24: float | None = None
    oi_notional_usdt: float | None = None
    funding_rate: float | None = None


@dataclass(frozen=True)
class MoverRow:
    side: str  # GAINER | LOSER
    rank: int
    symbol: str
    day_open: float
    last_price: float
    change_pct: float
    fut_amount24: float | None
    oi_notional_usdt: float | None
    funding_rate: float | None


def compute_movers(liquid: list[MoverInput], top_n: int) -> list[MoverRow]:
    """Liquid contracts only (caller filters). Symbols without today's open or last price are
    skipped. Gainers: change desc; losers: change asc. A symbol may appear on one side only.
    """
    scored: list[tuple[float, MoverInput]] = []
    for item in liquid:
        change = pct_change(item.last_price, item.day_open)
        if change is not None:
            scored.append((change, item))
    gainers = sorted(scored, key=lambda x: (-x[0], x[1].symbol))[:top_n]
    losers = sorted(scored, key=lambda x: (x[0], x[1].symbol))[:top_n]

    def rows(side: str, pairs: list[tuple[float, MoverInput]]) -> list[MoverRow]:
        return [
            MoverRow(
                side=side,
                rank=rank,
                symbol=item.symbol,
                day_open=item.day_open or 0.0,
                last_price=item.last_price or 0.0,
                change_pct=change,
                fut_amount24=item.fut_amount24,
                oi_notional_usdt=item.oi_notional_usdt,
                funding_rate=item.funding_rate,
            )
            for rank, (change, item) in enumerate(pairs, start=1)
        ]

    return rows("GAINER", gainers) + rows("LOSER", losers)
