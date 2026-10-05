# TradingView parity fixtures (Phase 4)

`scripts/parity_check.py` compares the Python port with TradingView, bar by bar.

**How to export (one CSV per symbol x timeframe, 3 symbols x 5m / 15m / 1h):**
1. Open the MEXC perpetual chart (e.g. `MEXC:BTCUSDT.P`) on the timeframe, with **FGI Replica V3**
   (`agent-kit/reference/pine/fgi_replica_v3.pine`) added with its **default inputs**.
2. Scroll/load at least 2000 bars of history (the checker skips the first 500 as warm-up).
3. Chart menu → *Export chart data…* → time format ISO → export.
4. Save as `backend/tests/fixtures/tv/<SYMBOL>_<TF>.csv`, for example `BTCUSDT_5m.csv`,
   `ETHUSDT_15m.csv`, `SOLUSDT_1h.csv`. Keep the default column names (plot titles).

Compared columns: `R`, `S`, `M - downtrend` / `M - uptrend` (relative error <= 1e-6), `EMA 1/2/3`
(<= 1e-6), `VWAP` (<= 1e-6), `Consolidated trend` is not compared, and the events `bullT`, `bearT`,
`BUY`, `SELL`, `TD bull`, `TD bear`, `r`/`s` letters (exact, same bar; the "(against 4H)" variants are
merged because the HTF tag is the documented deviation from live `request.security`).
