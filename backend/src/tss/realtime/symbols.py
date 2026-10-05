"""Which symbols get live ticks: the latest selection plus pinned symbols (Arch §10)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tss.db.repositories import contracts as contracts_repo
from tss.db.repositories import discovery as discovery_repo


async def live_symbols(session_factory: async_sessionmaker[AsyncSession]) -> set[str]:
    async with session_factory() as session:
        momentum = await discovery_repo.latest_momentum(session)
        active = await contracts_repo.active_contracts(session)
    selected = {r.symbol for r in momentum if r.selection_rank is not None}
    pinned = {c.symbol for c in active if c.pinned}
    return selected | pinned
