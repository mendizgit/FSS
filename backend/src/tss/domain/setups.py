"""Long / Short entry signal (pure). One definition shared by the API (dashboard tabs) and alerts.

Pine v3 entry on the last closed 15m bar:
  base  = 1H M trend agrees (mandatory), >= min_other_factors of the 4 others (local
          SuperTrend, close vs EMA1, divergence, sweep & engulf), and Parabolic SAR agrees
          (close above / below);
  final = base and StochRSI K vs D on the last closed 5m bar agrees (K above D long, below short).
Long and short both true, or neither: no entry. The 4H SuperTrend is reported (against_htf) and
never filters. Events (BUY / SELL / BULL_T / BEAR_T) are kept for the per-timeframe display only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

EVENTS = ("BUY", "SELL", "BULL_T", "BEAR_T")
BULL_EVENTS = frozenset({"BUY", "BULL_T"})
BEAR_EVENTS = frozenset({"SELL", "BEAR_T"})
BAR_MINUTES = {"5m": 5, "15m": 15, "1h": 60}
ENTRY_TF = "15m"
STOCH_TF = "5m"
MAX_BASE_AGE = timedelta(minutes=15)  # the 15m row may trail the 5m row by at most this
EVENT_MAX_BARS = 20  # events further back are not reported
EVENT_LOOKBACK = timedelta(hours=11)  # stored events read per run (covers 10 hourly bars)


@dataclass(frozen=True)
class EventRef:
    event: str
    bars_ago: int  # bars before the timeframe's newest closed bar
    against_htf: bool | None


@dataclass(frozen=True)
class TfView:
    timeframe: str
    bar_close_time: datetime  # newest closed bar of this timeframe
    m_trend: str  # UP | DOWN | NONE
    events: tuple[EventRef, ...]  # BUY / SELL / BULL_T / BEAR_T, newest first
    entry_long: bool | None = None  # base entry (SAR + score), NULL on pre-v3 rows
    entry_short: bool | None = None
    long_score: int | None = None
    short_score: int | None = None
    long_factors: str | None = None
    short_factors: str | None = None
    htf_dir: int | None = None  # 4H SuperTrend: -1 bull, 1 bear, 0 unknown
    stoch_dir: int | None = None  # 5m StochRSI K vs D: 1 / -1 / 0


@dataclass(frozen=True)
class Setup:
    bias: str  # long | short
    trigger_timeframe: str  # always the entry timeframe (15m)
    score: int  # factors met out of 5
    factors: str  # e.g. "ST,1H,EMA"
    trigger_bar_close_time: datetime  # close of the 15m bar the entry is based on
    against_htf: bool | None  # vs the 4H SuperTrend; informational only
    minutes_ago: int  # minutes since that 15m bar closed (at the newest 5m close)


def recent_events(
    bar_close_time: datetime,
    timeframe: str,
    stored: list[tuple[str, datetime, bool | None]],
    last_event: str,
    bars_ago: int | None,
    last_against_htf: bool | None,
) -> tuple[EventRef, ...]:
    """Stored events (event, bar_close_time, against_htf) plus the row's own newest event.

    Events are stored only from the 3 newest bars of each run, so the newest event is merged in
    from the full-history computation when it was never stored.
    """
    secs = BAR_MINUTES.get(timeframe, 5) * 60
    refs: list[EventRef] = []
    for event, closed_at, against in stored:
        ago = round((bar_close_time - closed_at).total_seconds() / secs)
        if 0 <= ago <= EVENT_MAX_BARS:
            refs.append(EventRef(event, ago, against))
    if (
        last_event in EVENTS
        and bars_ago is not None
        and bars_ago <= EVENT_MAX_BARS
        and not any(r.event == last_event and r.bars_ago == bars_ago for r in refs)
    ):
        refs.append(EventRef(last_event, bars_ago, last_against_htf))
    refs.sort(key=lambda r: r.bars_ago)
    return tuple(refs)


def _entry(base: TfView, stoch: TfView, bias: str) -> Setup | None:
    long = bias == "long"
    ok = base.entry_long if long else base.entry_short
    if not ok or stoch.stoch_dir != (1 if long else -1):
        return None
    score = (base.long_score if long else base.short_score) or 0
    factors = (base.long_factors if long else base.short_factors) or ""
    htf = base.htf_dir
    against = None if not htf else (htf != -1 if long else htf != 1)
    return Setup(
        bias=bias,
        trigger_timeframe=ENTRY_TF,
        score=score,
        factors=factors,
        trigger_bar_close_time=base.bar_close_time,
        against_htf=against,
        minutes_ago=round((stoch.bar_close_time - base.bar_close_time).total_seconds() / 60),
    )


def classify(views: list[TfView]) -> Setup | None:
    base = next((v for v in views if v.timeframe == ENTRY_TF), None)
    stoch = next((v for v in views if v.timeframe == STOCH_TF), None)
    if base is None or stoch is None:
        return None
    lag = stoch.bar_close_time - base.bar_close_time
    if lag < timedelta(0) or lag > MAX_BASE_AGE:
        return None  # rows are out of step (one timeframe stopped updating)
    long = _entry(base, stoch, "long")
    short = _entry(base, stoch, "short")
    if (long is None) == (short is None):
        return None  # neither, or both (conflict)
    return long or short
