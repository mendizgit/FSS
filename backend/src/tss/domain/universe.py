"""Universe and liquidity rules (Arch §4). Pure functions."""

from __future__ import annotations

from collections.abc import Collection


def in_universe(
    quote: str, settle: str, state: int, quote_asset: str, denylist: Collection[str], symbol: str
) -> bool:
    """USDT-quoted and settled, state 0 (enabled, per MEXC docs), not denylisted."""
    return quote == quote_asset and settle == quote_asset and state == 0 and symbol not in denylist


def zero_fee(maker: float | None, taker: float | None) -> bool | None:
    """True only if both fee rates are 0; None when either is not returned (unknown)."""
    if maker is None or taker is None:
        return None
    return maker == 0 and taker == 0


def oi_notional_usdt(
    hold_vol: float | None, contract_size: float | None, fair_price: float | None
) -> float | None:
    """holdVol x contractSize x fairPrice; None if any input is missing."""
    if hold_vol is None or contract_size is None or fair_price is None:
        return None
    return hold_vol * contract_size * fair_price


def is_liquid(
    amount24: float | None,
    oi_notional: float | None,
    min_turnover_24h: float,
    min_oi_notional: float,
) -> bool:
    """Gate 1: both conditions must hold; missing data means not liquid."""
    if amount24 is None or oi_notional is None:
        return False
    return amount24 >= min_turnover_24h and oi_notional >= min_oi_notional


def spot_symbol_for(base_coin: str, quote_asset: str, spot_symbols: Collection[str]) -> str | None:
    """BASE + QUOTE if that spot market exists (e.g. BTC + USDT -> BTCUSDT), else None."""
    candidate = f"{base_coin}{quote_asset}"
    return candidate if candidate in spot_symbols else None
