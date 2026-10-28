"""FGI Replica V3 composed from the primitives (port of reference/pine/fgi_replica_v3.pine).

`compute` runs the whole engine over closed bars of one timeframe and returns per-bar arrays
(used by the parity check and the event scan). `snapshot` reads the newest bar into the values
stored in `signals`.

Higher-timeframe values (4H SuperTrend direction, 1H range-filter M trend) come from the last
CLOSED higher-timeframe bar at each bar's close: a documented deviation from live
`request.security`, which repaints.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from tss.indicators.divergence import DivParams, single_pivot_divergence
from tss.indicators.primitives import (
    NAN,
    Series,
    atr,
    ema,
    highest,
    isnan,
    lowest,
    rsi,
    sar,
    stoch_rsi,
    vwap_daily,
)
from tss.indicators.range_filter import RangeFilterParams, range_filter
from tss.indicators.supertrend import supertrend
from tss.indicators.zones import ZoneParams, zone_position, zones

EVENTS = ("BUY", "SELL", "BULL_T", "BEAR_T", "TD_BULL", "TD_BEAR")  # priority within one bar


@dataclass(frozen=True)
class FgiParams:
    rf: RangeFilterParams = field(default_factory=RangeFilterParams)
    rsi_len: int = 14
    use_gate: bool = True
    gate_bars: int = 20
    buy_os: float = 30.0
    sell_ob: float = 70.0
    ema1: int = 6
    ema2: int = 24
    ema3: int = 32
    st_mult: float = 2.168
    st_len: int = 8
    g_rsi_len: int = 14
    g_div_len: int = 3
    min_other: int = 2  # entry: factors needed besides the mandatory 1H M trend (of 4)
    sar_start: float = 0.02
    sar_inc: float = 0.02
    sar_max: float = 0.2
    sr_rsi_len: int = 14
    sr_stoch_len: int = 14
    sr_k: int = 3
    sr_d: int = 3
    l1_in: float = 0.025
    l1_rsi_r: float = 60.8
    l1_rsi_s: float = 36.0
    div: DivParams = field(default_factory=DivParams)
    zone: ZoneParams = field(default_factory=ZoneParams)


@dataclass(frozen=True)
class Bars:
    """Closed bars of one timeframe, oldest first."""

    open_time: list[datetime]
    open: Series
    high: Series
    low: Series
    close: Series
    volume: Series

    def __len__(self) -> int:
        return len(self.close)


@dataclass(frozen=True)
class HtfContext:
    """Higher-timeframe values aligned to each signal bar (0 until a closed bar exists)."""

    htf_dir: list[int]  # SuperTrend direction of the 4H series: -1 bull, 1 bear, 0 unknown
    com_trend: list[int]  # range-filter M trend of the 1H series: 1 up, -1 down, 0 unknown


def align(
    signal_close_times: Sequence[datetime],
    htf_open_times: Sequence[datetime],
    htf_delta: timedelta,
    values: Sequence[float],
    missing: float = NAN,
) -> list[float]:
    """Value of the last higher-timeframe bar that has CLOSED at or before each signal bar's
    close (two-pointer; no lookahead)."""
    out: list[float] = []
    j = -1
    for t in signal_close_times:
        while j + 1 < len(htf_open_times) and htf_open_times[j + 1] + htf_delta <= t:
            j += 1
        out.append(values[j] if j >= 0 else missing)
    return out


def build_htf_context(
    signal: Bars,
    signal_delta: timedelta,
    bars_1h: Bars,
    bars_4h: Bars,
    params: FgiParams | None = None,
) -> HtfContext:
    p = params or FgiParams()
    close_times = [t + signal_delta for t in signal.open_time]
    _, dir4 = supertrend(bars_4h.high, bars_4h.low, bars_4h.close, p.st_mult, p.st_len)
    atr4 = atr(bars_4h.high, bars_4h.low, bars_4h.close, p.st_len)
    # a direction is only meaningful once its ATR exists (Pine: na until warmed up)
    dir4_f = [float(d) if not isnan(a) else NAN for d, a in zip(dir4, atr4, strict=True)]
    com = range_filter(bars_1h.high, bars_1h.low, bars_1h.close, p.rf).trend
    d4 = timedelta(hours=4)
    d1 = timedelta(hours=1)
    htf_dir = align(close_times, bars_4h.open_time, d4, dir4_f)
    com_trend = align(close_times, bars_1h.open_time, d1, [float(t) for t in com], 0.0)
    return HtfContext(
        htf_dir=[0 if isnan(d) else int(d) for d in htf_dir],
        com_trend=[int(t) for t in com_trend],
    )


@dataclass
class FgiSeries:
    """Per-bar results (index-aligned with the input bars)."""

    line_m: Series
    line_r: Series
    line_s: Series
    trend: list[int]
    rsi: Series
    ema1: Series
    ema2: Series
    ema3: Series
    loc_dir: list[int]
    htf_dir: list[int]
    ct_buy_count: list[int]
    ct_sell_count: list[int]
    bull_t: list[bool]
    bear_t: list[bool]
    buy: list[bool]
    sell: list[bool]
    td_bull: list[bool]
    td_bear: list[bool]
    r_letter: list[bool]
    s_letter: list[bool]
    long_score: list[int]
    short_score: list[int]
    long_factors: list[str]
    short_factors: list[str]
    sar: Series
    entry_long: list[bool]  # base entry: 1H M trend, >= min_other other factors, SAR (no StochRSI)
    entry_short: list[bool]
    zone_c: Series
    zone_b: Series
    vwap: Series
    st_line: Series = field(default_factory=list)


def _div(a: float, b: float) -> float:
    return a / b if b != 0 else NAN


def compute(bars: Bars, htf: HtfContext, params: FgiParams | None = None) -> FgiSeries:
    p = params or FgiParams()
    n = len(bars)
    o, h, lo, c = bars.open, bars.high, bars.low, bars.close
    rf = range_filter(h, lo, c, p.rf)
    rsi_d = rsi(c, p.rsi_len)
    rsi_low = lowest(rsi_d, p.gate_bars + 1)
    rsi_high = highest(rsi_d, p.gate_bars + 1)

    bull_t = [i > 0 and rf.trend[i] == 1 and rf.trend[i - 1] == -1 for i in range(n)]
    bear_t = [i > 0 and rf.trend[i] == -1 and rf.trend[i - 1] == 1 for i in range(n)]
    buy = [bull_t[i] and (not p.use_gate or rsi_low[i] <= p.buy_os) for i in range(n)]
    sell = [bear_t[i] and (not p.use_gate or rsi_high[i] >= p.sell_ob) for i in range(n)]

    ema1 = ema(c, p.ema1)
    ema2 = ema(c, p.ema2)
    ema3 = ema(c, p.ema3)
    _, loc_dir = supertrend(h, lo, c, p.st_mult, p.st_len)
    loc_bull = [d < 0 for d in loc_dir]
    loc_bear = [d > 0 for d in loc_dir]

    ct_up = [ema1[i] > ema2[i] for i in range(n)]
    buy_count: list[int] = []
    sell_count: list[int] = []
    bc = sc = 0
    for up in ct_up:
        if up:
            bc, sc = bc + 1, 0
        else:
            sc, bc = sc + 1, 0
        buy_count.append(bc)
        sell_count.append(sc)
    td_bull: list[bool] = []
    td_bear: list[bool] = []
    for i in range(n):
        prev_up = ct_up[i - 1] if i > 0 else False
        prev_bull = loc_bull[i - 1] if i > 0 else False
        prev_bear = loc_bear[i - 1] if i > 0 else False
        ct_bull_flip = ct_up[i] and not prev_up
        ct_bear_flip = (not ct_up[i]) and prev_up
        st_bull_flip = loc_bull[i] and not prev_bull
        st_bear_flip = loc_bear[i] and not prev_bear
        td_bull.append((ct_bull_flip or st_bull_flip) and ct_up[i] and loc_bull[i])
        td_bear.append((ct_bear_flip or st_bear_flip) and (not ct_up[i]) and loc_bear[i])

    # --- entry score: 5 factors (local SuperTrend, 1H M trend, close vs EMA1, divergence,
    # sweep & engulf) and the mandatory Parabolic SAR gate ---
    rec_sweep_bull: list[bool] = []
    rec_sweep_bear: list[bool] = []
    rs_bull = rs_bear = False
    sb_bar = sr_bar = 0
    for i in range(n):
        if i > 0:
            if lo[i] < lo[i - 1] and c[i] > h[i - 1] and c[i] > o[i]:
                rs_bull, sb_bar = True, i
            if h[i] > h[i - 1] and c[i] < lo[i - 1] and c[i] < o[i]:
                rs_bear, sr_bar = True, i
        if i - sb_bar > 5:
            rs_bull = False
        if i - sr_bar > 5:
            rs_bear = False
        rec_sweep_bull.append(rs_bull)
        rec_sweep_bear.append(rs_bear)
    g_rsi = rsi(c, p.g_rsi_len)
    div_bull, div_bear = single_pivot_divergence(g_rsi, h, lo, p.g_div_len)
    sar_line = sar(h, lo, c, p.sar_start, p.sar_inc, p.sar_max)

    long_score: list[int] = []
    short_score: list[int] = []
    long_factors: list[str] = []
    short_factors: list[str] = []
    entry_long: list[bool] = []
    entry_short: list[bool] = []
    for i in range(n):
        lf = [
            (loc_bull[i], "ST"),
            (htf.com_trend[i] == 1, "1H"),
            (c[i] > ema1[i], "EMA"),
            (div_bull[i], "DIV"),
            (rec_sweep_bull[i], "SWP"),
        ]
        sf = [
            (loc_bear[i], "ST"),
            (htf.com_trend[i] == -1, "1H"),
            (c[i] < ema1[i], "EMA"),
            (div_bear[i], "DIV"),
            (rec_sweep_bear[i], "SWP"),
        ]
        long_factors.append(",".join(name for ok, name in lf if ok))
        short_factors.append(",".join(name for ok, name in sf if ok))
        long_score.append(sum(1 for ok, _ in lf if ok))
        short_score.append(sum(1 for ok, _ in sf if ok))
        entry_long.append(
            htf.com_trend[i] == 1 and long_score[i] - 1 >= p.min_other and c[i] > sar_line[i]
        )
        entry_short.append(
            htf.com_trend[i] == -1 and short_score[i] - 1 >= p.min_other and c[i] < sar_line[i]
        )

    # --- s / r letters ---
    r_letter = [False] * n
    s_letter = [False] * n
    for i in range(1, n):
        hw = rf.line_r[i] - rf.line_m[i]
        prev_beyond_r = c[i - 1] > rf.line_r[i - 1]
        prev_beyond_s = c[i - 1] < rf.line_s[i - 1]
        line_r, line_s = rf.line_r[i], rf.line_s[i]
        r1_ = (
            prev_beyond_r
            and h[i] > line_r
            and c[i] < line_r - p.l1_in * hw
            and rsi_d[i - 1] > p.l1_rsi_r
        )
        s1_ = (
            prev_beyond_s
            and lo[i] < line_s
            and c[i] > line_s + p.l1_in * hw
            and rsi_d[i - 1] < p.l1_rsi_s
        )
        r_letter[i] = bool(r1_)
        s_letter[i] = bool(s1_)

    zc, zb = zones(h, lo, c, rf.moved, p.zone)
    hlc3 = [(h[i] + lo[i] + c[i]) / 3.0 for i in range(n)]
    vwap = vwap_daily(bars.open_time, hlc3, bars.volume)
    return FgiSeries(
        line_m=rf.line_m,
        line_r=rf.line_r,
        line_s=rf.line_s,
        trend=rf.trend,
        rsi=rsi_d,
        ema1=ema1,
        ema2=ema2,
        ema3=ema3,
        loc_dir=loc_dir,
        htf_dir=htf.htf_dir,
        ct_buy_count=buy_count,
        ct_sell_count=sell_count,
        bull_t=bull_t,
        bear_t=bear_t,
        buy=buy,
        sell=sell,
        td_bull=td_bull,
        td_bear=td_bear,
        r_letter=r_letter,
        s_letter=s_letter,
        zone_c=zc,
        zone_b=zb,
        vwap=vwap,
        long_score=long_score,
        short_score=short_score,
        long_factors=long_factors,
        short_factors=short_factors,
        sar=sar_line,
        entry_long=entry_long,
        entry_short=entry_short,
    )


def event_at(s: FgiSeries, i: int) -> str | None:
    """The event on bar i (priority BUY > SELL > BULL_T > BEAR_T > TD_BULL > TD_BEAR)."""
    flags = {
        "BUY": s.buy[i],
        "SELL": s.sell[i],
        "BULL_T": s.bull_t[i],
        "BEAR_T": s.bear_t[i],
        "TD_BULL": s.td_bull[i],
        "TD_BEAR": s.td_bear[i],
    }
    for name in EVENTS:
        if flags[name]:
            return name
    return None


def against_htf(s: FgiSeries, i: int, event: str) -> bool | None:
    """True if the event on bar i goes against the 4H trend (the Pine "x" tag). TD events and
    unknown HTF are not tagged."""
    if event in ("BUY", "BULL_T"):
        return not (s.htf_dir[i] < 0)
    if event in ("SELL", "BEAR_T"):
        return not (s.htf_dir[i] > 0)
    return None


@dataclass(frozen=True)
class SignalSnapshot:
    bar_close_time: datetime
    m_trend: str
    last_event: str
    bars_ago: int | None
    against_htf: bool | None
    zone_position: str | None
    price_vs_vwap: str | None
    htf_dir: int  # 4H SuperTrend: -1 bull, 1 bear, 0 unknown
    long_score: int
    short_score: int
    long_factors: str
    short_factors: str
    entry_long: bool
    entry_short: bool


def snapshot(
    bars: Bars,
    s: FgiSeries,
    tf_delta: timedelta,
    params: FgiParams | None = None,
) -> SignalSnapshot:
    """Values for the newest (closed) bar."""
    p = params or FgiParams()
    i = len(bars) - 1
    last_event = "NONE"
    bars_ago: int | None = None
    against: bool | None = None
    for j in range(i, -1, -1):
        ev = event_at(s, j)
        if ev is not None:
            last_event, bars_ago, against = ev, i - j, against_htf(s, j, ev)
            break
    c = bars.close[i]
    vw = s.vwap[i]
    return SignalSnapshot(
        bar_close_time=bars.open_time[i] + tf_delta,
        m_trend="UP" if s.trend[i] == 1 else "DOWN" if s.trend[i] == -1 else "NONE",
        last_event=last_event,
        bars_ago=bars_ago,
        against_htf=against,
        zone_position=zone_position(c, s.zone_c[i], s.zone_b[i], p.zone),
        price_vs_vwap=None if isnan(vw) else ("ABOVE" if c >= vw else "BELOW"),
        htf_dir=s.htf_dir[i],
        long_score=s.long_score[i],
        short_score=s.short_score[i],
        long_factors=s.long_factors[i],
        short_factors=s.short_factors[i],
        entry_long=s.entry_long[i],
        entry_short=s.entry_short[i],
    )


def stoch_direction(close: Sequence[float], params: FgiParams | None = None) -> int:
    """StochRSI K vs D on the newest closed bar: 1 K above D, -1 K below D, 0 equal / unknown."""
    p = params or FgiParams()
    k, d = stoch_rsi(close, p.sr_rsi_len, p.sr_stoch_len, p.sr_k, p.sr_d)
    if not close or isnan(k[-1]) or isnan(d[-1]):
        return 0
    return 1 if k[-1] > d[-1] else -1 if k[-1] < d[-1] else 0


def recent_events(
    bars: Bars, s: FgiSeries, tf_delta: timedelta, last_k: int
) -> list[tuple[datetime, str, bool | None]]:
    """Events on the newest `last_k` closed bars: (bar close time, event, against_htf)."""
    out: list[tuple[datetime, str, bool | None]] = []
    n = len(bars)
    for j in range(max(0, n - last_k), n):
        ev = event_at(s, j)
        if ev is not None:
            out.append((bars.open_time[j] + tf_delta, ev, against_htf(s, j, ev)))
    return out
