"""Helpers shared by the 15-minute pipeline agents."""

from __future__ import annotations

from datetime import datetime

from tss.core.time import floor_to_minutes
from tss.db.models import Contract, MarketSnapshot
from tss.domain.calculations import BAR


def expected_last_closed(now: datetime) -> datetime:
    """open_time of the newest bar that must be closed at `now`."""
    return floor_to_minutes(now, 15) - BAR


def target_symbols(
    contracts: list[Contract], snapshots: dict[str, MarketSnapshot]
) -> tuple[set[str], set[str]]:
    """(liquid symbols, pinned symbols) among active contracts, from the latest snapshots."""
    liquid = {
        c.symbol for c in contracts if (s := snapshots.get(c.symbol)) is not None and s.liquid
    }
    pinned = {c.symbol for c in contracts if c.pinned}
    return liquid, pinned
