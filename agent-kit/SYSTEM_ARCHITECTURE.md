# System Architecture — Trading Signal System (TSS)

Status: **Approved v1.1** (2026-10-05). This version uses MEXC as the only data source; CMC was removed. Follow this document unless a contradiction or technical blocker is found. See §15.

---

## 1. Overview

```text
            ┌───────────── Ubuntu host (Docker Compose) ───────────────────────────┐
            │                                                                       │
MEXC REST ──┼─► worker (Python)                                                     │
 RSS/News ──┼─►  ├─ Control Agent (scheduler, health, circuit breakers)            │
            │    ├─ Universe Builder        (Discovery, every 6 h)                  │
            │    ├─ Snapshot Collector      (every 5 min)                           │
            │    ├─ Market Movers           (every 5 min, after snapshot)           │
            │    ├─ Kline Sync → Movers Pool → Momentum Selection (every 15 min)    │
            │    ├─ Classification Agent    (every 15 min, same cycle)              │
            │    ├─ News Agent              (every 15 min)                          │
            │    ├─ Signal Agent            (Phase 4, every 5 min)                  │
            │    └─ Telegram Notifier       (Phase 5)                               │
            │            │ writes                                                   │
            │            ▼                                                          │
            │      PostgreSQL ──── LISTEN/NOTIFY ────►  api (FastAPI)               │
            │                                           ├─ REST /api/*              │
 MEXC WS ───┼──────────────────────────────────────────►├─ Live ticker gateway      │
            │                                           └─ WebSocket /ws            │
            │                    web (Next.js, Node) ─────────┤                     │
            │                    proxy (Caddy, host :8088, basic auth) ◄── LAN only ──────┼── Windows PC
            └───────────────────────────────────────────────────────────────────────┘
```

### Agent naming (original brief → implementation)

| Brief | Implementation |
|---|---|
| Discovery Agent | Universe Builder + Kline Sync + Movers Pool (top 50) |
| Sorting Agent | Momentum Selection (top 20) + Classification Agent |
| Control Agent | Control Agent |
| Signal / Technical Agent | Signal Agent (Phase 4) |
| News Agent | News Agent |
| Web Agent | `api` + `web` + `proxy` |
| (new) | Market Movers (UTC-day top 10 gainers / losers) |

### Process separation

`worker` runs all agents. `api` serves data and real-time events. A worker crash never takes down the dashboard; the UI shows stale or failed status instead.

---

## 2. Technology stack

All components are open source.

| Layer | Technology | Notes |
|---|---|---|
| Backend language | Python 3.12 | managed with **uv** |
| HTTP client | httpx (async) | shared client, timeouts, retries, rate limiter |
| WebSocket client | websockets | MEXC futures WS (live ticker only) |
| Scheduler | APScheduler 3.x (AsyncIOScheduler) | in `worker` |
| API | FastAPI + Uvicorn | REST + WebSocket |
| Validation / settings | Pydantic v2, pydantic-settings | |
| ORM / migrations | SQLAlchemy 2.0 (async) + asyncpg, Alembic | |
| Numerics | pandas, numpy | indicators **hand-implemented** to match Pine |
| News | feedparser | RSS |
| Logging | structlog (JSON) + secret-redaction processor | |
| Lint / type | ruff, mypy | |
| Calc checks | pytest | calculations, classification, Pine parity only |
| Database | PostgreSQL 17 | plain tables |
| Frontend | Next.js (latest stable, App Router), React, TypeScript strict | Node.js current LTS, **pnpm** |
| UI | Tailwind CSS, shadcn/ui, lucide-react | |
| Data fetching | TanStack Query + native WebSocket | |
| Reverse proxy | Caddy 2 | single LAN port, basic auth, WS proxying |
| Runtime | Docker Compose | `db`, `worker`, `api`, `web`, `proxy` |

**Not used (by design):**

- CMC or any second market-data provider
- Redis, Celery, Kafka, TimescaleDB
- `tradingview-ta`
- order-flow, footprint, CVD or order-book processing

---

## 3. External data sources

**Every endpoint and field marked ⚠ must be verified by `scripts/preflight.py` (Phase 0) against official MEXC docs and live responses.** If a path or field differs, apply `EXECUTION_RULES.md` §7.

### 3.1 MEXC Futures — public, **no API key**

Base URL: `https://contract.mexc.com` ⚠

| Use | Endpoint | Cadence |
|---|---|---|
| Contract catalogue: `symbol`, `baseCoin`, `quoteCoin`, `settleCoin`, `contractSize`, `state`, fee fields (`makerFeeRate`/`takerFeeRate` ⚠ if returned) | `GET /api/v1/contract/detail` | every 6 h |
| All tickers: `lastPrice`, `fairPrice`, `holdVol` (OI in contracts), `fundingRate`, `volume24`, `amount24` ⚠ | `GET /api/v1/contract/ticker` (no symbol = all) | every 5 min |
| Klines `Min15` (sync), `Min5`/`Min60`/`Hour4` (P4) | `GET /api/v1/contract/kline/{symbol}?interval=&start=&end=` (`time` in **seconds**; the last bar returned may still be forming, so drop it) ⚠ max bars per call | incremental |
| Live ticker | WS `wss://contract.mexc.com/edge`, `sub.ticker` per symbol, ping ≤ 20 s ⚠ | continuous (`api` process) |

- Notional OI = `holdVol × contractSize × fairPrice`.
- The following are **not available** publicly:
  - Liquidation feed: always shown as `unavailable`.
  - OI history: built from our own 5-min snapshots.

### 3.2 MEXC Spot — public, **no API key**, optional per symbol

Base URL: `https://api.mexc.com` ⚠

| Use | Endpoint |
|---|---|
| 24 h tickers (all) | `GET /api/v3/ticker/24hr` |
| Klines 15m (selected + pinned only) | `GET /api/v3/klines?symbol=BASEUSDT&interval=15m` ⚠ |

If a symbol has no spot market, its spot fields are `NULL` with reason `no_spot_market`.

### 3.3 News

- **RSS (no key):** CoinDesk, Cointelegraph, Decrypt, The Block. URLs are listed in `config/news_sources.yaml` and verified in preflight.
- **CryptoPanic (optional):** requires `CRYPTOPANIC_API_KEY`. It is enabled only if the key is present and preflight succeeds. It is non-critical because its free-tier terms are unverified.

### 3.4 Telegram (Phase 5)

Bot API with `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`. The user must `/start` the bot to obtain a `chat_id`.

---

## 4. Universe & liquidity

### Universe (every 6 h)

All MEXC contracts with `quoteCoin = USDT`, `settleCoin = USDT`, and state `0` (enabled).

- MEXC docs (Get Contract Info): `state` 0 enabled, 1 delivery, 2 delivered, 3 offline, 4 paused. Preflight (2026-10-05): all 1186 returned contracts have `state = 0`. The universe filter is `quoteCoin = USDT`, `settleCoin = USDT` and `state == 0`.

- **Nothing is excluded by asset type.** BTC and ETH are included.
- `config/denylist.yaml` exists for manual exclusions and is **empty by default**.
- Stablecoin-pair perps, if any exist, naturally fail the momentum gate.

### Liquidity gate (Gate 1)

Evaluated every snapshot from ticker data. A contract is `liquid` when both conditions hold:

- `amount24 ≥ liquidity.min_turnover_24h_usdt` (**$1,000,000**)
- `oi_notional_usdt ≥ liquidity.min_oi_notional_usdt` (**$500,000**)

### Pinned symbols

`universe.pinned_symbols` = `[BTC_USDT, ETH_USDT]`.

- They are **always** kline-synced, classified and shown as "Market context" rows.
- They do not take any of the top-20 slots.
- They can also qualify for the top 20 on merit; in that case they are shown once, in the context section, marked "selected".

### Zero-fee badge

`zero_fee = true` only when both returned fee fields equal 0. Otherwise `NULL` (unknown, fields not returned) or `false`. The badge is display-only and never used as a filter.

---

## 5. Calculations

All formulas live in `tss/domain/` as pure functions.

**Shared rules:**

- `pct_change(now, then) = ((now / then) − 1) × 100`. Returns `None` if `then` is missing or ≤ 0.
- Snapshot matching at T − Δ: use the nearest snapshot within ±`snapshot_match_tolerance_s` (default 90 s). Otherwise the value is `None` with reason `history_unavailable`.

### 5.1 Snapshots (every 5 min, aligned to :00, :05, …)

- One futures ticker call and one spot 24 h ticker call cover the whole universe.
- Stored fields: `last_price`, `fair_price`, `hold_vol`, `oi_notional_usdt`, `funding_rate`, `fut_volume24`, `fut_amount24`, `liquid`, `spot_price`, `spot_quote_volume24`.

### 5.2 Kline sync (every 15 min at :00/:15/:30/:45 + 20 s)

- Applies to liquid contracts plus pinned symbols.
- On the first run per symbol, backfill `kline.backfill_bars` (200) `Min15` bars. After that, fetch only bars newer than the latest stored one (plus one, for correction).
- Store **closed bars only** in `klines_15m`. Bar `B` is closed when `B.open_time + 15 min ≤ now`.
- Daily open: `daily_opens(symbol, utc_date) = open` of the 00:00 UTC `Min15` bar. This is taken from the forming bar when the sync runs at 00:00:20, or from the backfill on cold start.
- Gap detection: record a missing `open_time` as a gap and set the `kline_gap` reliability reason.

### 5.3 Movers Pool — top 50 (Discovery)

For every liquid contract, using `klines_15m`:

```text
price_change_15m_pct = pct_change(close[last_closed], close[last_closed − 1])
rvol_15m             = amount[last_closed] / median(amount[last_closed − 96 … last_closed − 1])
```

- `rvol_15m` is `None` if fewer than `momentum.rvol_lookback_bars` (96) prior bars exist, or if the median is 0.
- **Pool:** rank by `rvol_15m` desc (tie-break: |price_change_15m_pct| desc) and take the top `momentum.pool_size` (50).

### 5.4 Momentum selection — top 20 (Gate 2)

- Keep pool members with `|price_change_15m_pct| ≥ 1.5` **AND** `rvol_15m ≥ 1.5`.
- Rank by `rvol_15m` desc and take the top `momentum.top_n` (20).
- If fewer qualify, select fewer. **Never backfill.**
- Pinned symbols are added for classification regardless of the result.

### 5.5 Classification inputs per window W ∈ {1h, 4h}

These apply to selected and pinned symbols.

| Metric | Source | Formula |
|---|---|---|
| `price_change_W_pct` | `klines_15m` | close[last_closed] vs close[last_closed − n] (n = 4 / 16) |
| `fut_volume_change_W_pct` | `klines_15m` | Σ amount(last n) vs Σ amount(previous n) |
| `spot_volume_change_W_pct` | spot 15m klines | same, using quote volume; `NULL` if no spot market |
| `oi_change_W_pct` | snapshots | `pct_change(hold_vol_now, hold_vol_W_ago)` |
| `funding_now` | snapshot | `funding_rate` |
| `funding_delta_W` | snapshots | `funding_now − funding_W_ago` |

**Direction:**

- `RISING` if change > +deadband
- `FALLING` if change < −deadband
- `FLAT` otherwise

### 5.6 Market movers — UTC day (every 5 min, after snapshot)

For liquid contracts only:

```text
utc_day_change_pct = pct_change(last_price_snapshot, daily_opens[today].open)
```

- **Gainers:** top `movers.top_n` (10) by change desc.
- **Losers:** top 10 by change asc.
- If today's open is missing, skip that symbol.
- If no opens exist yet, set status to `WAITING_DAY_OPEN` (only possible in the first 20 s after 00:00 UTC).
- **IST note:** the day boundary is 00:00 UTC (05:30 IST). IST is display-only and never changes any calculation.

---

## 6. Classification rules (state-based, no scoring)

Rules are evaluated per symbol and per window. Step 1 always runs first.

**Step 1 — UNRELIABLE.** A symbol is UNRELIABLE if any of these hold:

- the newest snapshot is older than `stale_after_s` (600)
- a required metric is missing (price, futures volume, OI)
- the contract is not liquid
- a kline gap exists inside the window

All reasons are recorded.

**Step 2 — State.** Otherwise:

| State | Price | OI | Futures volume | Meaning |
|---|---|---|---|---|
| `LONG_BUILDUP` | RISING | RISING | RISING | Trend confirmation (long) |
| `SHORT_BUILDUP` | FALLING | RISING | RISING | Short build-up / liquidation risk |
| `SHORT_COVERING` | RISING | FALLING | any | Short squeeze / covering |
| `LONG_UNWINDING` | FALLING | FALLING | any | Long liquidation / weak trend |
| `NEUTRAL` | — | — | — | None of the above |

**Flags** (informational, multiple allowed):

| Flag | Rule |
|---|---|
| `FUNDING_CONFIRMS` | LONG_BUILDUP and funding_delta RISING, **or** SHORT_BUILDUP and funding_delta FALLING |
| `CROWDED_LONG` | `funding_now ≥ classification.crowded_long_funding` |
| `CROWDED_SHORT` | `funding_now ≤ classification.crowded_short_funding` |
| `SQUEEZE_RISK` | (SHORT_COVERING or SHORT_BUILDUP) and CROWDED_SHORT |
| `SPOT_CONFIRMED` | spot volume RISING |
| `TF_CONFLICT` | the 1h and 4h states point in opposite directions |
| `WARMING_UP` | OI/funding history is shorter than W |
| `LIQUIDATIONS_UNAVAILABLE` | always set |

**Mapping to the original brief:**

| Brief term | Equivalent |
|---|---|
| Uptrend | `LONG_BUILDUP` + `SPOT_CONFIRMED` |
| Downtrend | `SHORT_BUILDUP` + `SPOT_CONFIRMED` |
| Short-squeeze | `SHORT_COVERING` + `CROWDED_SHORT` |
| Unreliable | `UNRELIABLE` |

---

## 7. Signal engine (Phase 4 — gated)

The signal engine is a Python port of `agent-kit/reference/pine/fgi_replica_v3.pine`. See `skills/pine-port.md`.

- **Symbols:** selected + pinned.
- **Timeframes:** 5m, 15m, 1h. Context timeframes: 1h and 4h.
- **History:** ≥ 1000 closed bars per timeframe, with a 500-bar warm-up. Paginate if the kline limit is lower ⚠.
- **Closed bars only.** HTF values come from the last closed HTF bar; this deviation from Pine is documented.
- **Outputs:**
  - `m_trend`
  - `last_event` (BUY | SELL | BULL_T | BEAR_T | TD_BULL | TD_BEAR | NONE), with `bars_ago` and `against_htf`
  - `htf_supertrend`, `local_supertrend`
  - `consolidated_trend`
  - long/short score (0–6) and grade
  - `rsi_divergence`
  - `sr_letter`
  - `zone_position`
  - `price_vs_vwap`
- **Licence:** the Range Filter and divergence ports are MPL-2.0. Keep the attribution header.

---

## 8. Scheduling (Control Agent)

| Job | Trigger (UTC) | Depends on | Critical |
|---|---|---|---|
| Preflight | startup | — | yes |
| Universe Builder | startup + every 6 h | preflight | yes (first run) |
| Snapshot Collector | `*/5` at :00 s | universe | yes |
| Market Movers | after each snapshot | snapshot, daily_opens | no |
| **15-min pipeline:** Kline Sync → Movers Pool → Momentum Selection → Classification | `*/15` at +20 s, one `cycle_id` | snapshots, universe | yes |
| News Agent | every 15 min | — | no |
| Signal Agent (P4) | `*/5` at +30 s | latest selection | no |
| Telegram (P5) | on new signal event | signal | no |
| Retention purge | daily 00:30 | — | no |

- **Cycle budget:** the 15-min pipeline must finish within `control.cycle_budget_s` (240 s). On overrun, log a warning and continue. Never start a second instance (`max_instances=1`).
- **Run records:** every job writes an `agent_runs` row (`RUNNING`, `SUCCESS`, `PARTIAL`, `FAILED`, `SKIPPED`, `HALTED`) and then sends `NOTIFY tss_events`.
- **Failure policy:**
  - **Retry:** 3 attempts with backoff of 2 s, 4 s and 8 s plus jitter, on network errors, 5xx and 429. Honour `Retry-After`.
  - **Circuit breaker:** per agent. It opens after 3 consecutive failed runs and cools down for 900 s.
  - **Degraded mode:** a non-critical failure marks that panel `STALE`; the rest of the system continues.
  - **Critical halt:** triggered when the DB is unreachable, config is invalid, the universe is empty, or the MEXC futures breaker is open. The system enters `HALTED`, dependent jobs stop, and recovery is polled every 60 s.

---

## 9. Data model (PostgreSQL, all `timestamptz` UTC)

| Table | Key columns |
|---|---|
| `agent_runs` | id, agent, cycle_id, started_at, finished_at, status, rows_in, rows_out, selected_count, error_component, error_phase, error_message, meta jsonb |
| `system_state` | id=1, state (`RUNNING`/`DEGRADED`/`HALTED`/`WARMING_UP`), reason, updated_at |
| `contracts` | symbol PK (`BASE_USDT`), base_coin, quote_coin, settle_coin, contract_size, state, maker_fee_rate NULL, taker_fee_rate NULL, zero_fee NULL, denylisted bool, pinned bool, spot_symbol NULL, updated_at |
| `market_snapshots` | (symbol, ts) PK, last_price, fair_price, hold_vol, oi_notional_usdt, funding_rate, fut_volume24, fut_amount24, liquid bool, spot_price NULL, spot_quote_volume24 NULL |
| `klines_15m` | (symbol, open_time) PK, open, high, low, close, volume, amount |
| `daily_opens` | (symbol, utc_date) PK, open |
| `momentum_rankings` | cycle_id, ts, symbol, pool_rank, price_change_15m_pct, rvol_15m, passed_gate2 bool, selection_rank NULL, pinned bool |
| `classifications` | cycle_id, ts, symbol, window, price_change_pct, oi_change_pct, fut_volume_change_pct, spot_volume_change_pct NULL, funding_now, funding_delta, state, flags text[], unreliable_reasons text[] |
| `market_movers` | ts, side (`GAINER`/`LOSER`), rank, symbol, day_open, last_price, change_pct, fut_amount24, oi_notional_usdt, funding_rate |
| `signals` (P4) | symbol, timeframe, bar_close_time, m_trend, last_event, bars_ago, against_htf, htf_supertrend, local_supertrend, consolidated_trend, long_score, short_score, long_grade, short_grade, rsi_divergence, sr_letter, zone_position, price_vs_vwap, computed_at; unique(symbol, timeframe, bar_close_time) |
| `signal_events` (P4) | symbol, timeframe, bar_close_time, event, against_htf, notified_at NULL; unique(symbol, timeframe, bar_close_time, event) |
| `news_items` | id, source, title, url UNIQUE, published_at, symbols text[], fetched_at |

- **Indexes:** `market_snapshots(ts)`, `klines_15m(open_time)`, `classifications(ts, symbol)`, `market_movers(ts)`, `agent_runs(agent, started_at desc)`.
- **Retention:** rows older than `RETENTION_DAYS` (5) are purged. `klines_15m` keeps at least `kline.backfill_bars` per symbol so RVOL stays computable.
- **Expected size:** about 300 liquid contracts × 96 bars/day × 5 days ≈ 144k kline rows, and ≈ 0.4M snapshot rows. Total **< 1 GB**.

---

## 10. API contract (FastAPI, prefix `/api`, read-only)

| Method | Path | Returns |
|---|---|---|
| GET | `/api/health` | liveness + DB check |
| GET | `/api/status` | system_state, latest run per agent, next run, universe/liquid counts, DB size |
| GET | `/api/discovery/latest` | latest cycle: movers pool (50) with `passed_gate2` and `selection_rank`, plus pinned symbols |
| GET | `/api/universe/summary` | counts: total, active, liquid, denylisted, zero-fee |
| GET | `/api/classification/latest?window=1h\|4h` | latest classification rows (selected + pinned) |
| GET | `/api/classification/{symbol}/history?window=&hours=` | time series for one symbol |
| GET | `/api/movers/latest` | top 10 gainers + top 10 losers, UTC day |
| GET | `/api/signals/latest` (P4) | latest signal per symbol × timeframe |
| GET | `/api/news?limit=50&symbol=` | news, newest first |
| GET | `/api/config/thresholds` | effective thresholds (no secrets) |
| WS | `/ws` | events below |

**WebSocket events** use the shape `{type, ts, data}`:

- `ticker` (≤ 1/s per symbol)
- `agent_status`
- `cycle_complete`
- `movers_updated`
- `news_new`
- `signal_new` (P4)
- `system_state`

**Conventions:**

- Timestamps are ISO-8601 UTC.
- Errors are returned as `{error:{code,message,component}}`.
- The live ticker gateway subscribes to selected + pinned symbols and re-subscribes on `cycle_complete`. Ticks are not persisted.

---

## 11. Frontend

There is a single route, `/`. The layout:

| Region | Content |
|---|---|
| **Top** | Status bar: system state; per-agent chips (status, last run IST, duration, rows, selected count, next run); universe/liquid counts; WS indicator |
| **Left** | Classification panel: pinned BTC/ETH "Market context" rows at the top, then the selected ≤ 20. 1h/4h toggle, sortable table, state badges, flag chips, zero-fee badge, detail drawer with history sparkline. A secondary tab shows the full movers pool (50) with RVOL and gate result. |
| **Middle** | **Signals** panel (Phase 4; before that it shows a "Signal engine not enabled" module state). Below it, **Market Movers**: Top 10 Gainers \| Top 10 Losers, labelled "Since 00:00 UTC (05:30 IST)". |
| **Right** | News feed |

**Breakpoints:**

- ≥ 1280 px: 3 columns.
- 768–1279 px: left + middle, news below.
- < 768 px: tabs (Classification, Signals/Movers, News).

**Other requirements:**

- All times are shown in IST with an "IST" suffix; the tooltip shows UTC.
- `robots: noindex`.
- No external runtime CDNs.
- The footer notice "Market analysis only — not financial advice" is always visible.

---

## 12. Security

- **LAN only:**
  - Caddy publishes `<UBUNTU_LAN_IP>:8088`.
  - `ufw` allows the port only from `LAN_CLIENT_IP`.
  - `db`, `api` and `web` are not published.
- **Access control:** Caddy basic auth (bcrypt hash in env).
- **No exchange API key:** all MEXC data used is public. Private and trading endpoints are never called.
- **Secrets** (`CRYPTOPANIC_API_KEY`, `TELEGRAM_*`, DB password, basic-auth hash):
  - `.env` is mode 600 and gitignored.
  - Settings use `SecretStr`; a structlog redaction processor and header stripping are applied.
- **Security headers via Caddy:** CSP, `X-Frame-Options DENY`, `Referrer-Policy no-referrer`, `nosniff`.
- **API surface:** read-only, with Pydantic validation on all parameters.
- **Dependency audit:** `pip-audit` and `pnpm audit` in each phase report.

---

## 13. Configuration

| File | Content |
|---|---|
| `.env` | `CRYPTOPANIC_API_KEY` (opt), `TELEGRAM_BOT_TOKEN` (P5), `TELEGRAM_CHAT_ID` (P5), `DATABASE_URL`, `POSTGRES_*`, `BASIC_AUTH_USER`, `BASIC_AUTH_HASH`, `UBUNTU_LAN_IP`, `LAN_CLIENT_IP`, `DISPLAY_TZ=Asia/Kolkata`, `RETENTION_DAYS=5`, `LOG_LEVEL` |
| `config/thresholds.yaml` | see below |
| `config/denylist.yaml` | `symbols: []` (empty by default) |
| `config/news_sources.yaml` | RSS URLs, enable flags, symbol-tagging stoplist |

`config/thresholds.yaml` (values marked † are proposed defaults, tunable after observation):

```yaml
universe:
  quote_asset: USDT
  refresh_hours: 6
  pinned_symbols: [BTC_USDT, ETH_USDT]
signals:
  majors: [BTC_USDT, ETH_USDT, SOL_USDT, XRP_USDT]   # always computed; dashboard "Majors" tab
liquidity:
  min_turnover_24h_usdt: 1000000
  min_oi_notional_usdt: 500000
kline:
  interval: Min15
  backfill_bars: 200
momentum:
  pool_size: 50
  rvol_lookback_bars: 96
  min_rvol: 1.5
  min_abs_price_change_15m_pct: 1.5
  top_n: 20
  rank_by: rvol_15m
movers:
  top_n: 10
  period: utc_day
classification:
  windows: [1h, 4h]
  deadband: { price_pct: 0.2, oi_pct: 0.5, volume_pct: 0.0, funding_delta: 0.0 }   # †
  crowded_long_funding: 0.0005      # † 0.05 % per funding interval
  crowded_short_funding: -0.0005    # †
  stale_after_s: 600
  snapshot_match_tolerance_s: 90
control:
  cycle_budget_s: 240
  breaker_failures: 3
  breaker_cooldown_s: 900
mexc:
  max_requests_per_second: 5        # † conservative; adjust after preflight
```

---

## 14. Key decisions (ADR summary)

| # | Decision | Reason |
|---|---|---|
| 1 | **MEXC is the only market-data source; CMC removed** | User trades only on MEXC; fewer failure points; no key or credit budget |
| 2 | Liquidity gate (turnover $1M + OI $500k) replaces the market-cap filter | Measures tradable liquidity directly |
| 3 | RVOL ≥ 1.5× replaces the bar-to-bar 1.5 % volume change | The bar-to-bar figure is noise; RVOL detects real spikes |
| 4 | Funnel: universe → liquid → pool 50 (RVOL) → gate 2 → top 20 | Clear, explainable selection |
| 5 | Nothing excluded by type; BTC/ETH pinned as context | BTC/ETH moves drive altcoins |
| 6 | Market movers use the 00:00 UTC open; IST is display-only | Matches the exchange daily candle |
| 7 | State-based classification with flags, no score | User decision; the Signal Agent decides the move |
| 8 | OI/funding history from own snapshots | MEXC has no public OI history |
| 9 | Separate `worker` / `api`; PostgreSQL LISTEN/NOTIFY | Fault isolation; no broker |
| 10 | Hand-ported indicators | Exact Pine parity |
| 11 | Order flow / footprint / CVD out of scope | Heavy to compute and render; keeps scope achievable |
| 12 | Local Docker Compose + Caddy | LAN-only requirement |

---

## 15. Architecture change rule

Do not change this architecture during implementation unless one of the following applies:

- a requirement cannot be implemented safely
- a requirement conflicts with this document
- the MEXC API contradicts §3

In any of these cases, describe the conflict and ask the user. On approval, update this file and the ADR table in the same commit.
