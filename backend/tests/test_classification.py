from tss.core.settings import ClassificationCfg, DeadbandCfg
from tss.domain.classification import (
    ClassificationResult,
    Reliability,
    WindowMetrics,
    classify,
    with_tf_conflict,
)

CFG = ClassificationCfg(
    windows=["1h", "4h"],
    deadband=DeadbandCfg(price_pct=0.2, oi_pct=0.5, volume_pct=0.0, funding_delta=0.0),
    crowded_long_funding=0.0005,
    crowded_short_funding=-0.0005,
    stale_after_s=600,
    snapshot_match_tolerance_s=90,
)
OK = Reliability(snapshot_stale=False, liquid=True, kline_gap=False, oi_history_covers_window=True)


def m(price=1.0, oi=1.0, vol=1.0, spot=None, funding=0.0001, fdelta=0.0):  # type: ignore[no-untyped-def]
    return WindowMetrics(price, oi, vol, spot, funding, fdelta)


def test_state_table() -> None:
    assert classify(m(1, 1, 1), OK, CFG).state == "LONG_BUILDUP"
    assert classify(m(-1, 1, 1), OK, CFG).state == "SHORT_BUILDUP"
    assert classify(m(1, -1, -5), OK, CFG).state == "SHORT_COVERING"  # volume any
    assert classify(m(-1, -1, 5), OK, CFG).state == "LONG_UNWINDING"  # volume any
    assert classify(m(1, 1, -1), OK, CFG).state == "NEUTRAL"  # OI up, volume falling
    assert classify(m(0.1, 1, 1), OK, CFG).state == "NEUTRAL"  # price inside deadband
    assert classify(m(1, 0.3, 1), OK, CFG).state == "NEUTRAL"  # OI inside deadband


def test_unreliable_first_and_all_reasons_recorded() -> None:
    bad = Reliability(
        snapshot_stale=True, liquid=False, kline_gap=True, oi_history_covers_window=True
    )
    res = classify(m(None, None, None), bad, CFG)
    assert res.state == "UNRELIABLE"
    assert res.unreliable_reasons == [
        "snapshot_stale",
        "missing_price",
        "missing_futures_volume",
        "missing_oi",
        "not_liquid",
        "kline_gap",
    ]
    assert "LIQUIDATIONS_UNAVAILABLE" in res.flags


def test_warming_up_flag_and_reason() -> None:
    warm = Reliability(False, True, False, oi_history_covers_window=False)
    res = classify(m(1, None, 1), warm, CFG)
    assert res.state == "UNRELIABLE" and res.unreliable_reasons == ["history_unavailable"]
    assert "WARMING_UP" in res.flags


def test_flags() -> None:
    res = classify(m(1, 1, 1, spot=2.0, funding=0.0006, fdelta=0.0001), OK, CFG)
    assert res.state == "LONG_BUILDUP"
    assert res.flags == [
        "LIQUIDATIONS_UNAVAILABLE",
        "FUNDING_CONFIRMS",
        "CROWDED_LONG",
        "SPOT_CONFIRMED",
    ]
    short = classify(m(-1, 1, 1, funding=-0.0006, fdelta=-0.0001), OK, CFG)
    assert short.state == "SHORT_BUILDUP"
    assert {"FUNDING_CONFIRMS", "CROWDED_SHORT", "SQUEEZE_RISK"} <= set(short.flags)
    cover = classify(m(1, -1, 1, funding=-0.0005), OK, CFG)  # boundary is inclusive
    assert cover.state == "SHORT_COVERING" and {"CROWDED_SHORT", "SQUEEZE_RISK"} <= set(cover.flags)
    assert "SPOT_CONFIRMED" not in classify(m(1, 1, 1, spot=None), OK, CFG).flags


def test_tf_conflict() -> None:
    up = ClassificationResult("LONG_BUILDUP", ["X"], [])
    down = ClassificationResult("LONG_UNWINDING", [], [])
    out = with_tf_conflict({"1h": up, "4h": down})
    assert "TF_CONFLICT" in out["1h"].flags and "TF_CONFLICT" in out["4h"].flags
    same = with_tf_conflict({"1h": up, "4h": ClassificationResult("SHORT_COVERING", [], [])})
    assert "TF_CONFLICT" not in same["1h"].flags
    neutral = with_tf_conflict({"1h": up, "4h": ClassificationResult("NEUTRAL", [], [])})
    assert "TF_CONFLICT" not in neutral["1h"].flags
