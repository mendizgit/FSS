"""State-based classification (Arch §6). Pure functions; no scoring.

Step 1 (UNRELIABLE) always runs first and records every reason. Step 2 maps price / OI /
futures-volume directions to a state. Flags are informational.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tss.core.settings import ClassificationCfg
from tss.domain.calculations import Direction, direction

UNRELIABLE = "UNRELIABLE"
NEUTRAL = "NEUTRAL"

BULLISH_STATES = frozenset({"LONG_BUILDUP", "SHORT_COVERING"})
BEARISH_STATES = frozenset({"SHORT_BUILDUP", "LONG_UNWINDING"})


@dataclass(frozen=True)
class WindowMetrics:
    price_change_pct: float | None
    oi_change_pct: float | None
    fut_volume_change_pct: float | None
    spot_volume_change_pct: float | None
    funding_now: float | None
    funding_delta: float | None


@dataclass(frozen=True)
class Reliability:
    snapshot_stale: bool
    liquid: bool
    kline_gap: bool
    oi_history_covers_window: bool


@dataclass(frozen=True)
class ClassificationResult:
    state: str
    flags: list[str] = field(default_factory=list)
    unreliable_reasons: list[str] = field(default_factory=list)


def unreliable_reasons(m: WindowMetrics, r: Reliability) -> list[str]:
    reasons: list[str] = []
    if r.snapshot_stale:
        reasons.append("snapshot_stale")
    if m.price_change_pct is None:
        reasons.append("missing_price")
    if m.fut_volume_change_pct is None:
        reasons.append("missing_futures_volume")
    if m.oi_change_pct is None:
        reasons.append("history_unavailable" if not r.oi_history_covers_window else "missing_oi")
    if not r.liquid:
        reasons.append("not_liquid")
    if r.kline_gap:
        reasons.append("kline_gap")
    return reasons


def _state(price: Direction, oi: Direction, volume: Direction) -> str:
    if price == Direction.RISING and oi == Direction.RISING and volume == Direction.RISING:
        return "LONG_BUILDUP"
    if price == Direction.FALLING and oi == Direction.RISING and volume == Direction.RISING:
        return "SHORT_BUILDUP"
    if price == Direction.RISING and oi == Direction.FALLING:
        return "SHORT_COVERING"
    if price == Direction.FALLING and oi == Direction.FALLING:
        return "LONG_UNWINDING"
    return NEUTRAL


def classify(m: WindowMetrics, r: Reliability, cfg: ClassificationCfg) -> ClassificationResult:
    flags: list[str] = []
    if not r.oi_history_covers_window:
        flags.append("WARMING_UP")
    flags.append("LIQUIDATIONS_UNAVAILABLE")  # always: no public liquidation feed

    reasons = unreliable_reasons(m, r)
    if reasons:
        return ClassificationResult(UNRELIABLE, flags, reasons)

    db = cfg.deadband
    price = direction(m.price_change_pct, db.price_pct)
    oi = direction(m.oi_change_pct, db.oi_pct)
    volume = direction(m.fut_volume_change_pct, db.volume_pct)
    if price is None or oi is None or volume is None:  # unreachable: reasons covered above
        return ClassificationResult(UNRELIABLE, flags, ["missing_metric"])
    state = _state(price, oi, volume)

    funding_delta = direction(m.funding_delta, db.funding_delta)
    crowded_long = m.funding_now is not None and m.funding_now >= cfg.crowded_long_funding
    crowded_short = m.funding_now is not None and m.funding_now <= cfg.crowded_short_funding
    if (state == "LONG_BUILDUP" and funding_delta == Direction.RISING) or (
        state == "SHORT_BUILDUP" and funding_delta == Direction.FALLING
    ):
        flags.append("FUNDING_CONFIRMS")
    if crowded_long:
        flags.append("CROWDED_LONG")
    if crowded_short:
        flags.append("CROWDED_SHORT")
    if state in ("SHORT_COVERING", "SHORT_BUILDUP") and crowded_short:
        flags.append("SQUEEZE_RISK")
    if direction(m.spot_volume_change_pct, db.volume_pct) == Direction.RISING:
        flags.append("SPOT_CONFIRMED")
    return ClassificationResult(state, flags, [])


def with_tf_conflict(results: dict[str, ClassificationResult]) -> dict[str, ClassificationResult]:
    """Add TF_CONFLICT to both windows when the 1h and 4h states point in opposite directions
    (bullish: LONG_BUILDUP, SHORT_COVERING; bearish: SHORT_BUILDUP, LONG_UNWINDING).
    """
    one, four = results.get("1h"), results.get("4h")
    if one is None or four is None:
        return results
    opposite = (one.state in BULLISH_STATES and four.state in BEARISH_STATES) or (
        one.state in BEARISH_STATES and four.state in BULLISH_STATES
    )
    if not opposite:
        return results
    return {
        w: ClassificationResult(res.state, [*res.flags, "TF_CONFLICT"], res.unreliable_reasons)
        for w, res in results.items()
    }
