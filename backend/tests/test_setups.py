"""Long / Short setup rule (domain/setups.py): pure, no database."""

from datetime import UTC, datetime, timedelta

from tss.domain.setups import EventRef, TfView, classify, recent_events

T = datetime(2026, 10, 7, 10, 0, tzinfo=UTC)


def view(tf: str, trend: str, *events: tuple[str, int, bool | None]) -> TfView:
    return TfView(tf, T, trend, tuple(EventRef(e, ago, against) for e, ago, against in events))


def test_long_needs_1h_confirmation_and_a_fresh_lower_timeframe_event() -> None:
    views = [
        view("5m", "UP", ("BULL_T", 2, False)),
        view("15m", "UP"),
        view("1h", "UP", ("BUY", 7, None)),
    ]
    s = classify(views)
    assert s is not None and s.bias == "long"
    assert (s.trigger_timeframe, s.trigger_event, s.trigger_bars_ago) == ("5m", "BULL_T", 2)
    assert (s.htf_event, s.htf_bars_ago, s.minutes_ago) == ("BUY", 7, 10)
    assert s.trigger_bar_close_time == T - timedelta(minutes=10)


def test_short_is_the_mirror() -> None:
    s = classify([view("15m", "DOWN", ("SELL", 1, True)), view("1h", "DOWN", ("BEAR_T", 0, None))])
    assert s is not None and s.bias == "short" and s.trigger_timeframe == "15m"
    assert s.against_htf is True  # reported, not used as a filter


def test_windows_are_inclusive_and_exclusive_as_specified() -> None:
    htf = view("1h", "UP", ("BULL_T", 10, False))
    assert classify([view("5m", "UP", ("BUY", 5, False)), htf]) is not None  # 5m: 0-5 bars
    assert classify([view("5m", "UP", ("BUY", 6, False)), htf]) is None
    assert classify([view("15m", "UP", ("BUY", 2, False)), htf]) is not None  # 15m: 0-2 bars
    assert classify([view("15m", "UP", ("BUY", 3, False)), htf]) is None
    stale_htf = view("1h", "UP", ("BULL_T", 11, False))  # 1h: 0-10 bars
    assert classify([view("5m", "UP", ("BUY", 0, False)), stale_htf]) is None


def test_trend_and_event_direction_must_agree() -> None:
    htf = view("1h", "UP", ("BULL_T", 1, False))
    assert classify([view("5m", "DOWN", ("BUY", 0, False)), htf]) is None  # trend not Up
    assert classify([view("5m", "UP", ("SELL", 0, False)), htf]) is None  # bearish event
    assert (
        classify([view("5m", "UP", ("BUY", 0, False)), view("1h", "DOWN", ("BULL_T", 1, False))])
        is None
    )
    assert classify([view("5m", "UP", ("TD_BULL", 0, False)), htf]) is None  # TD is not a trigger


def test_fresher_trigger_wins_and_conflict_is_neutral() -> None:
    htf = view("1h", "UP", ("BULL_T", 1, False))
    s = classify([view("5m", "UP", ("BUY", 4, False)), view("15m", "UP", ("BUY", 0, True)), htf])
    assert s is not None and s.trigger_timeframe == "15m"  # 0 min beats 20 min
    # both a long and a short qualify (cannot happen with one 1h trend, but the rule is explicit)
    assert classify([view("5m", "UP"), htf]) is None


def test_recent_events_merges_the_rows_own_newest_event() -> None:
    five = timedelta(minutes=5)
    stored = [("BUY", T - 3 * five, False)]
    refs = recent_events(T, "5m", stored, "BULL_T", 1, True)
    assert [(r.event, r.bars_ago) for r in refs] == [("BULL_T", 1), ("BUY", 3)]
    # already stored: not duplicated; TD events and far-away events are ignored
    assert len(recent_events(T, "5m", stored, "BUY", 3, False)) == 1
    assert recent_events(T, "5m", [], "TD_BULL", 0, None) == ()
    assert recent_events(T, "5m", [("BUY", T - 30 * five, None)], "NONE", None, None) == ()
