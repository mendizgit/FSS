# Skill — Pine Script → Python Port (Phase 4)

## Role

Act as a quantitative developer porting `agent-kit/reference/pine/fgi_replica_v3.pine` to Python with bar-for-bar parity.

## Scope (port)

| Pine block | Python module | Output |
|---|---|---|
| Range Filter [DW] Type 1, Close, smooth, avg-changes (condEma) → M/R/S, `trend` | `range_filter.py` | m_trend, lineM/R/S, rfMoved |
| RSI gate → `buySig` / `sellSig`, `bullT` / `bearT` | `fgi_v3.py` | last_event |
| EMA 9/21/32, consolidated trend (2-bar confirm), TD | `fgi_v3.py` | consolidated_trend, TD events |
| SuperTrend(10, 3) local + 4H | `supertrend.py` | local/htf supertrend, against_htf |
| Confluence 6 factors + grades A ≥ 5, B ≥ 4 | `fgi_v3.py` | long/short score & grade |
| Single-pivot RSI divergence (sticky 20) and LonesomeTheBlue regular divergence | `divergence.py` | rsi_divergence |
| s/r letters (setups 1 and 2) | `fgi_v3.py` | sr_letter |
| Extreme zones (SMA 190 hl2, stdev 200 hlc3, step on rfMoved) | `zones.py` | zone_position |
| VWAP (daily reset 00:00 UTC) | `primitives.py` | price_vs_vwap |

Out of scope: all drawing (labels, lines, fills, table) and the daily/weekly level drawings.

## Pine semantics to replicate exactly

- `ta.ema`: seeded with the SMA of the first `length` values (Pine behaviour). Verify against fixtures.
- `ta.rma` (Wilder): alpha = 1/length, SMA seed. `ta.rsi` uses rma.
- `ta.atr` uses rma of the true range. `ta.supertrend` uses Pine's band-ratcheting rules and direction sign convention (dir < 0 = bullish).
- `ta.stdev` is the population (biased) stdev.
- `ta.pivothigh/low(left, right)` are confirmed `right` bars later. Never use future bars.
- `var` state and `x[1]` history: implement with explicit sequential loops (numba is optional, and only if the user approves) where state is path-dependent: range filter, condEma, sticky flags, counters.
- `na` handling: propagate `NaN`. Comparisons with `NaN` are false, as in Pine.
- HTF values come from the last **closed** higher-timeframe bar, aligned to each lower-timeframe bar close (no lookahead). This is a documented deviation from live Pine `request.security`.

## Parity check (required)

- Fixtures: the user exports TradingView chart data (CSV with OHLCV + indicator plots) for 3 symbols × 3 timeframes into `backend/tests/fixtures/tv/`.
- `scripts/parity_check.py` compares per bar after a 500-bar warm-up:
  - lineM/R/S: relative error ≤ 1e-6
  - EMAs/RSI: ≤ 1e-6
  - SuperTrend direction: exact
  - events (BUY/SELL/bullT/bearT/TD): exact match on the same bar
- Report mismatches with bar time and values. Do not tune formulas to hide mismatches; explain them.
- HTF-dependent outputs are compared only on bars where the HTF bar has closed.

## Licence

The Range Filter port and the divergence port derive from MPL-2.0 code. Keep the attribution header (original author, licence, URL) in `range_filter.py` and `divergence.py`.
