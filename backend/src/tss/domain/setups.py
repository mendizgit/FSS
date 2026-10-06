"""Long / Short setups (pure). One definition shared by the API (dashboard tabs) and the alerts.

Long: on 5m (event 0-5 bars ago) or 15m (0-2 bars ago) the M trend is Up and a BUY / bullT event
happened inside that window, and on 1h the M trend is Up with a BUY / bullT event 0-10 bars ago.
Short is the mirror (Down, SELL / bearT). Both or neither: no setup. The 4H trend is reported
(against_htf of the triggering event) but never used to accept or reject a setup.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

EVENTS = ("BUY", "SELL", "BULL_T", "BEAR_T")
BULL_EVENTS = frozenset({"BUY", "BULL_T"})
BEAR_EVENTS = frozenset({"SELL", "BEAR_T"})
BAR_MINUTES = {"5m": 5, "15m": 15, "1h": 60}
FRESH_MAX_BARS = {"5m": 5, "15m": 2}
HTF = "1h"
HTF_EVENT_MAX_BARS = 10
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


@dataclass(frozen=True)
class Setup:
    bias: str  # long | short
    trigger_timeframe: str
    trigger_event: str
    trigger_bars_ago: int
    trigger_bar_close_time: datetime
    against_htf: bool | None
    htf_event: str
    htf_bars_ago: int
    minutes_ago: int  # age of the trigger event


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


def _side(views: list[TfView], trend: str, events: frozenset[str], bias: str) -> Setup | None:
    htf = next((v for v in views if v.timeframe == HTF), None)
    if htf is None or htf.m_trend != trend:
        return None
    htf_ev = next(
        (e for e in htf.events if e.event in events and e.bars_ago <= HTF_EVENT_MAX_BARS), None
    )
    if htf_ev is None:
        return None
    best: Setup | None = None
    for view in views:
        max_bars = FRESH_MAX_BARS.get(view.timeframe)
        if max_bars is None or view.m_trend != trend:
            continue
        ev = next((e for e in view.events if e.event in events and e.bars_ago <= max_bars), None)
        if ev is None:
            continue
        minutes = ev.bars_ago * BAR_MINUTES[view.timeframe]
        if best is None or minutes < best.minutes_ago:
            best = Setup(
                bias=bias,
                trigger_timeframe=view.timeframe,
                trigger_event=ev.event,
                trigger_bars_ago=ev.bars_ago,
                trigger_bar_close_time=view.bar_close_time
                - timedelta(minutes=ev.bars_ago * BAR_MINUTES[view.timeframe]),
                against_htf=ev.against_htf,
                htf_event=htf_ev.event,
                htf_bars_ago=htf_ev.bars_ago,
                minutes_ago=minutes,
            )
    return best


def classify(views: list[TfView]) -> Setup | None:
    long = _side(views, "UP", BULL_EVENTS, "long")
    short = _side(views, "DOWN", BEAR_EVENTS, "short")
    if (long is None) == (short is None):
        return None  # neither, or both (conflict)
    return long or short
