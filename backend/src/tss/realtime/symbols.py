"""Which symbols get live ticks / signals (Arch §7, §10)."""

from __future__ import annotations

from collections.abc import Collection

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tss.db.repositories import contracts as contracts_repo
from tss.db.repositories import discovery as discovery_repo


async def live_symbols(
    session_factory: async_sessionmaker[AsyncSession], majors: Collection[str] = ()
) -> set[str]:
    """Symbols the signal engine works on: the latest selection, pinned symbols and the
    configured majors (only those that are active contracts)."""
    async with session_factory() as session:
        momentum = await discovery_repo.latest_momentum(session)
        active = await contracts_repo.active_contracts(session)
    active_symbols = {c.symbol for c in active}
    selected = {r.symbol for r in momentum if r.selection_rank is not None}
    pinned = {c.symbol for c in active if c.pinned}
    return selected | pinned | (set(majors) & active_symbols)


async def ticker_symbols(
    session_factory: async_sessionmaker[AsyncSession], majors: Collection[str] = ()
) -> set[str]:
    """Everything the dashboard shows a price for: signal symbols, the whole movers pool and
    the current top gainers / losers, so every visible price ticks live."""
    base = await live_symbols(session_factory, majors)
    async with session_factory() as session:
        pool = {r.symbol for r in await discovery_repo.latest_momentum(session)}
        movers = {m.symbol for m in await discovery_repo.latest_movers(session)}
    return base | pool | movers
