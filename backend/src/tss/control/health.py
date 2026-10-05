"""system_state evaluation (Arch §8). States: RUNNING, DEGRADED, HALTED, WARMING_UP."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

RUNNING, DEGRADED, HALTED, WARMING_UP = "RUNNING", "DEGRADED", "HALTED", "WARMING_UP"
WARMUP_WINDOW = timedelta(hours=4)  # the longest classification window needs 4 h of history


@dataclass
class HealthInputs:
    halt_reason: str | None
    open_breakers: list[str] = field(default_factory=list)
    degraded_agents: list[str] = field(default_factory=list)
    earliest_snapshot: datetime | None = None
    now: datetime | None = None


def evaluate(h: HealthInputs) -> tuple[str, str | None]:
    """Priority: HALTED > DEGRADED > WARMING_UP > RUNNING."""
    if h.halt_reason:
        return HALTED, h.halt_reason
    problems = [f"breaker open: {a}" for a in h.open_breakers] + [
        f"stale: {a}" for a in h.degraded_agents
    ]
    if problems:
        return DEGRADED, "; ".join(problems)
    if h.earliest_snapshot is None or (
        h.now is not None and h.now - h.earliest_snapshot < WARMUP_WINDOW
    ):
        return WARMING_UP, "snapshot history shorter than the 4h window"
    return RUNNING, None
