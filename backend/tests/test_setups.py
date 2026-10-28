"""15m entry signal rule (domain/setups.py): pure, no database."""

from datetime import UTC, datetime, timedelta

from tss.domain.setups import EventRef, TfView, classify, recent_events

T15 = datetime(2026, 10, 7, 10, 0, tzinfo=UTC)  # close of the 15m bar
T5 = T15 + timedelta(minutes=5)  # a newer 5m bar


def base(**kw: object) -> TfView:
    fields: dict[str, object] = {
        "entry_long": True,
        "entry_short": False,
        "long_score": 4,
        "short_score": 1,
        "long_factors": "ST,1H,EMA,DIV",
        "short_factors": "SWP",
        "htf_dir": -1,
    }
    return TfView("15m", T15, "UP", (), **{**fields, **kw})  # type: ignore[arg-type]


def stoch(direction: int, at: datetime = T5) -> TfView:
    return TfView("5m", at, "UP", (), stoch_dir=direction)


def test_long_needs_base_entry_and_5m_stoch_agreement() -> None:
    s = classify([base(), stoch(1)])
    assert s is not None and s.bias == "long" and s.trigger_timeframe == "15m"
    assert (s.score, s.factors, s.minutes_ago) == (4, "ST,1H,EMA,DIV", 5)
    assert s.trigger_bar_close_time == T15
    assert classify([base(), stoch(-1)]) is None  # K below D blocks a long
    assert classify([base(), stoch(0)]) is None
    assert classify([base(entry_long=False), stoch(1)]) is None  # SAR / score not met


def test_short_is_the_mirror() -> None:
    short = base(entry_long=False, entry_short=True, short_score=3, short_factors="1H,EMA,SWP")
    s = classify([short, stoch(-1)])
    assert s is not None and s.bias == "short" and s.score == 3
    assert classify([short, stoch(1)]) is None


def test_4h_trend_is_reported_never_a_filter() -> None:
    assert classify([base(htf_dir=-1), stoch(1)]).against_htf is False  # type: ignore[union-attr]
    assert classify([base(htf_dir=1), stoch(1)]).against_htf is True  # type: ignore[union-attr]
    assert classify([base(htf_dir=0), stoch(1)]).against_htf is None  # type: ignore[union-attr]
    short = base(entry_long=False, entry_short=True, htf_dir=1)
    assert classify([short, stoch(-1)]).against_htf is False  # type: ignore[union-attr]


def test_rows_out_of_step_or_missing_give_no_entry() -> None:
    assert classify([base()]) is None  # no 5m row
    assert classify([stoch(1)]) is None  # no 15m row
    assert classify([base(), stoch(1, T15 - timedelta(minutes=5))]) is None  # 5m older than 15m
    assert classify([base(), stoch(1, T15 + timedelta(minutes=20))]) is None  # 15m row stale
    assert classify([base(), stoch(1, T15 + timedelta(minutes=15))]) is not None


def test_both_sides_true_is_a_conflict() -> None:
    both = base(entry_short=True)
    assert classify([both, stoch(1)]) is not None  # stoch picks one side only
    assert classify([base(entry_long=True, entry_short=True), stoch(0)]) is None


def test_pre_v3_rows_have_no_entry() -> None:
    legacy = TfView("15m", T15, "UP", ())
    assert classify([legacy, stoch(1)]) is None


def test_recent_events_merges_the_newest_event() -> None:
    stored = [("BUY", T15 - timedelta(minutes=30), False)]
    refs = recent_events(T15, "15m", stored, "BULL_T", 0, True)
    assert refs == (EventRef("BULL_T", 0, True), EventRef("BUY", 2, False))
