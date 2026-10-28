"""Import every model so Base.metadata is complete (Alembic autogenerate relies on this)."""

from tss.db.models.classification import Classification
from tss.db.models.contracts import Contract
from tss.db.models.fgi_paper import FgiPaperTrade
from tss.db.models.market import DailyOpen, Kline15m, MarketSnapshot
from tss.db.models.momentum import MomentumRanking
from tss.db.models.movers import MarketMover
from tss.db.models.news import NewsItem
from tss.db.models.ops import AgentRun, ControlFlag, SystemState
from tss.db.models.paper import PaperTrade
from tss.db.models.signals import Signal, SignalEvent, SignalSetup

__all__ = [
    "AgentRun",
    "Classification",
    "Contract",
    "ControlFlag",
    "DailyOpen",
    "FgiPaperTrade",
    "Kline15m",
    "MarketMover",
    "MarketSnapshot",
    "MomentumRanking",
    "NewsItem",
    "PaperTrade",
    "Signal",
    "SignalEvent",
    "SignalSetup",
    "SystemState",
]
