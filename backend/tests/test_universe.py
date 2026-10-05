import pytest

from tss.domain.universe import in_universe, is_liquid, oi_notional_usdt, spot_symbol_for, zero_fee


def test_in_universe() -> None:
    assert in_universe("USDT", "USDT", 0, "USDT", [], "BTC_USDT")
    assert not in_universe("USDT", "USDT", 3, "USDT", [], "X_USDT")  # offline
    assert not in_universe("USDC", "USDC", 0, "USDT", [], "X_USDC")
    assert not in_universe("USDT", "USDC", 0, "USDT", [], "X_USDT")
    assert not in_universe("USDT", "USDT", 0, "USDT", ["BTC_USDT"], "BTC_USDT")  # denylisted


def test_zero_fee_requires_both_returned_and_zero() -> None:
    assert zero_fee(0.0, 0.0) is True
    assert zero_fee(0.0, 0.0001) is False
    assert zero_fee(None, 0.0) is None
    assert zero_fee(0.0, None) is None


def test_oi_notional() -> None:
    # 1000 contracts x 0.0001 x 50000 = 5000 USDT
    assert oi_notional_usdt(1000, 0.0001, 50000) == pytest.approx(5000.0)
    assert oi_notional_usdt(None, 0.0001, 50000) is None


def test_liquidity_gate_boundaries() -> None:
    assert is_liquid(1_000_000, 500_000, 1_000_000, 500_000)  # >= on both
    assert not is_liquid(999_999.99, 500_000, 1_000_000, 500_000)
    assert not is_liquid(1_000_000, 499_999.99, 1_000_000, 500_000)
    assert not is_liquid(None, 500_000, 1_000_000, 500_000)


def test_spot_symbol_mapping() -> None:
    assert spot_symbol_for("BTC", "USDT", {"BTCUSDT"}) == "BTCUSDT"
    assert spot_symbol_for("NEW", "USDT", {"BTCUSDT"}) is None
