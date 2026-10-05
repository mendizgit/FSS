"""Sanitised MEXC payload fixtures parse into the typed client models (EXECUTION_RULES §8)."""

import json
from pathlib import Path

from tss.clients.mexc_futures import envelope_data, parse_items
from tss.clients.models import ContractDetail, FuturesTicker, SpotTicker
from tss.domain.universe import is_liquid, oi_notional_usdt, zero_fee

FIX = Path(__file__).parent / "fixtures"


def load(name: str) -> object:
    return json.loads((FIX / name).read_text())


def test_contract_detail_fixture() -> None:
    data = envelope_data(load("mexc_contract_detail.json"), "/detail", "t")
    contracts = parse_items(ContractDetail, data, "/detail", "t")
    btc = next(c for c in contracts if c.symbol == "BTC_USDT")
    assert (btc.quoteCoin, btc.settleCoin, btc.state) == ("USDT", "USDT", 0)
    assert zero_fee(btc.makerFeeRate, btc.takerFeeRate) is False  # taker fee is not zero


def test_ticker_and_oi_notional_fixture() -> None:
    contracts = {
        c.symbol: c
        for c in parse_items(
            ContractDetail, envelope_data(load("mexc_contract_detail.json"), "/d", "t"), "/d", "t"
        )
    }
    tickers = parse_items(
        FuturesTicker, envelope_data(load("mexc_ticker.json"), "/t", "t"), "/t", "t"
    )
    btc = next(t for t in tickers if t.symbol == "BTC_USDT")
    oi = oi_notional_usdt(btc.holdVol, contracts["BTC_USDT"].contractSize, btc.fairPrice)
    assert oi is not None and oi > 1e9  # BTC open interest is in the billions of USDT
    assert is_liquid(btc.amount24, oi, 1_000_000, 500_000)


def test_spot_ticker_strings_become_numbers() -> None:
    spot = parse_items(SpotTicker, load("mexc_spot_ticker.json"), "/s", "t")
    assert all(isinstance(s.lastPrice, float) and isinstance(s.quoteVolume, float) for s in spot)
