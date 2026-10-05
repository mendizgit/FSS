# Feature Blueprint — Trading Signal System (TSS)

This is the feature-level source of truth. Formulas, thresholds and schemas live in `SYSTEM_ARCHITECTURE.md` (referenced as "Arch §n") and are not repeated here.

**Users / roles (all features):** one local operator, protected by LAN restriction plus basic auth. There are no in-app roles. The API is read-only.

## Phase plan

| Phase | Features | Gate |
|---|---|---|
| P0 Foundation | F0 | user review |
| P1 Data pipeline | F1, F2, F3, F4, F5, F11, F12 (data) | user review |
| P2 Dashboard | F6, F7 (incl. F12 UI) | user review |
| P3 News | F8 | user review |
| P4 Signal engine | F9 | **explicit user go-ahead required** |
| P5 Telegram | F10 | **explicit user go-ahead required** |

Out of scope: order flow, footprint, CVD, order book analysis, any non-MEXC market-data source, trading.

---

## F0 — Platform foundation

**Objective:** A runnable skeleton with config, logging, errors, DB, migrations and a MEXC/news preflight.

**Flow:**

1. Scaffold the repo per `PROJECT_STRUCTURE.md`.
2. Start Postgres via `docker-compose.dev.yml`.
3. Create an Alembic baseline covering all tables in Arch §9 except P4/P5.
4. Run `scripts/preflight.py`.

**Requirements:**

- `core/settings.py`
  - Uses pydantic-settings; secrets are typed `SecretStr`.
  - Loads YAML config and validates it at startup.
  - If config is invalid, exits with a component-named error.
- `core/logging.py`
  - structlog JSON output with a redaction processor.
  - Binds `component`, `phase`, `op` and `cycle_id` to each log line.
- `core/errors.py`
  - `TSSError(component, phase, operation, message, context)`.
  - Subclasses: `DataSourceError`, `ValidationError`, `CalculationError`, `ConfigError`, `StorageError`.
- `core/time.py`: UTC now, cron alignment helpers, UTC-day helpers, IST formatter.

**Preflight output:** a table, no secrets. Each item ✓/✗ with reason.

- **MEXC futures `contract/detail`**
  - reachable
  - fields present: `symbol`, `baseCoin`, `quoteCoin`, `settleCoin`, `contractSize`, `state`
  - state values and their meaning
  - fee fields present?
  - count of active USDT perps
- **MEXC futures `ticker`**
  - reachable
  - fields present: `lastPrice`, `fairPrice`, `holdVol`, `fundingRate`, `amount24`
  - estimated liquid count at current thresholds
- **MEXC futures `kline`**
  - interval names (`Min5`, `Min15`, `Min60`, `Hour4`)
  - maximum bars per call
  - whether the forming bar is included
  - time unit (seconds vs ms)
- **MEXC spot:** ticker and 15m kline reachability.
- **MEXC WS:** connect, subscribe to one ticker, receive one message, close.
- **RSS:** each source reachable. CryptoPanic is checked only if its key is present.

**Acceptance:**

- `alembic upgrade head` succeeds.
- Preflight completes.
- `ruff`, `mypy`, `pnpm lint`, `type-check` and `build` pass.
- `.env.example`, `.gitignore`, the README skeleton and the `CLAUDE.md` commands are verified.

---

## F1 — Universe Builder (Discovery)

**Objective:** Maintain the set of active MEXC USDT perpetual contracts.

**Flow:**

1. Fetch `contract/detail`.
2. Filter: USDT quote and settle, active state.
3. Apply `denylist.yaml` (empty by default).
4. Mark `pinned` (BTC_USDT, ETH_USDT).
5. Compute `zero_fee`.
6. Map `spot_symbol` using the spot exchange symbol list (ticker set).
7. Upsert `contracts`.
8. Record the run.

**Business rules:**

- Nothing is excluded by asset type.
- Contracts that become inactive are marked `state` and drop out of all downstream jobs.
- If fee fields are absent, `zero_fee = NULL`. Never assume a value.

**Acceptance:** `/api/universe/summary` returns total, active, liquid, denylisted and zero-fee counts.

---

## F2 — Snapshot Collector

**Objective:** Store a 5-minute market state for the whole universe. This feeds liquidity, OI/funding history and the movers' last price.

**Flow:** Every 5 min:

1. One futures ticker call and one spot ticker call.
2. Compute `oi_notional_usdt` and `liquid` (Arch §4).
3. Bulk insert `market_snapshots`.
4. Trigger F12.

**Business rules:**

- Idempotent per `(symbol, ts)`, with `ts` aligned to the 5-minute boundary.
- If there is no spot market, spot fields are `NULL`.
- Liquidations are not collected.

**Acceptance:** A row exists every 5 min per active contract. A missed tick is logged with the component name.

---

## F3 — Kline Sync, Movers Pool & Momentum Selection (Discovery → Sorting)

**Objective:** Every 15 minutes:

- rank the **top 50 movers pool** by RVOL
- select **up to 30** momentum candidates (|Δp 15m| ≥ 0.8 % and RVOL ≥ 1.2×; v1.3.3)
- always include BTC and ETH as pinned context

**Flow:** Runs in one `cycle_id`:

1. Kline sync for liquid and pinned contracts (Arch §5.2). This also writes `daily_opens`.
2. Compute `price_change_15m_pct` and `rvol_15m` (Arch §5.3).
3. Rank the pool (top 50).
4. Apply Gate 2 and select the top 20 (Arch §5.4).
5. Persist `momentum_rankings`.
6. Hand the selection plus pinned symbols to F4.

**Displayed fields (discovery list):**

- symbol, zero-fee badge, last price
- 15m change %, RVOL
- 24h turnover, OI notional, funding
- UTC-day change %
- pool rank, passed gate (✓/✗), selection rank

**Business rules:**

- Never backfill to 20.
- RVOL is `None` (and the contract is skipped for ranking) if there are fewer than 96 prior bars.
- On first start, the backfill (200 bars) makes RVOL available immediately. There is no 24-hour warm-up.

**Acceptance:** `/api/discovery/latest` returns the pool of up to 50 with gate results, refreshed every 15 min. The selection rules match Arch §5.3–5.4 exactly.

---

## F4 — Derivatives Classification (Sorting)

**Objective:** Classify each selected and pinned symbol on 1h and 4h windows into a state with flags.

**Flow:**

1. Fetch spot 15m klines for symbols with a spot market.
2. Compute the metrics (Arch §5.5).
3. Apply the rules (Arch §6).
4. Persist `classifications`.
5. `NOTIFY cycle_complete`.

**Displayed fields:**

- symbol (pinned rows labelled "Market context"), live price
- 15m %, 1h %, 4h % price change
- OI notional and OI change % (window)
- futures and spot volume change %
- funding now (%) and funding Δ
- state badge, flags, updated time (IST)

**Business rules:**

- UNRELIABLE is evaluated first, and all reasons are stored.
- `WARMING_UP` applies until OI history covers the window W (the 4h window needs 4 h of uptime).
- `LIQUIDATIONS_UNAVAILABLE` is always set.

**Acceptance:**

- Every selected and pinned symbol has a 1h row and a 4h row per cycle.
- Rules match Arch §6.
- The calculation unit checks pass.

---

## F5 — Control Agent

**Objective:** Schedule, coordinate, monitor and contain failures.

**Requirements:**

- Schedule per Arch §8.
- `cycle_id` propagation.
- `agent_runs` lifecycle.
- Retries and per-agent circuit breakers.
- Degraded vs critical-halt handling.
- Cycle budget warning.
- `system_state` updates.
- `NOTIFY` on every change.

**Acceptance:** Simulated failures behave per policy, and `/api/status` reflects them within one cycle. Simulations to cover:

- MEXC unreachable
- malformed response
- DB down
- cycle overrun

---

## F6 — Live Ticker Gateway

**Objective:** Real-time prices for selected and pinned symbols between cycles.

**Flow:**

1. The `api` process subscribes to the MEXC futures WS for each symbol.
2. Throttle to ≤ 1 update per second per symbol.
3. Broadcast `ticker` events on `/ws`.
4. Re-subscribe on `cycle_complete`.

**Business rules:**

- Reconnect with backoff.
- Keep the connection alive with pings.
- Do not persist ticks.

**Acceptance:** Prices update live, and the gateway recovers automatically after a network drop.

---

## F7 — Web Dashboard

**Objective:** A single-page real-time dashboard (Arch §11).

**UI requirements:**

- **Status bar (top)**
  - System state badge.
  - One chip per agent: Universe, Snapshots, Movers, Pipeline (Kline/Pool/Selection/Classification), News, Signals (P4). Each chip shows status, last run (IST), duration, rows, selected count and next run.
  - Universe and liquid counts.
  - WebSocket connection indicator.
- **Left — Classification**
  - Pinned BTC/ETH rows on top.
  - Selected rows below.
  - 1h/4h toggle.
  - Sortable columns; default sort is selection rank.
  - State badges use icon + text.
  - Flag chips with tooltips.
  - Stale rows are dimmed and show the reason.
  - Detail drawer with a history sparkline.
  - Tab "Movers pool (50)" showing RVOL and gate ✓/✗.
- **Middle — Signals (top)**
  - Shows the module state "Signal engine not enabled (Phase 4)" until F9 ships.
- **Middle — Market Movers (below signals)** — this is the F12 UI
  - Two lists side by side: Top 10 Gainers and Top 10 Losers.
  - Columns: rank, symbol, UTC-day change %, price, 24h turnover.
  - Header label: "Since 00:00 UTC (05:30 IST)".
- **Right — News**
  - Newest first.
  - Each item shows source, relative time and IST time, plus symbol chips.
  - Clicking a symbol chip filters the list.
  - Links use `rel="noopener noreferrer"`.
- **Footer notice:** removed at the user's request (2026-10-06).

**States:** loading skeletons, empty ("No symbols passed the momentum gate this cycle"), warming-up, error (showing the component name), stale.

**Acceptance:**

- Live updates arrive without manual refresh.
- Layout follows the breakpoints in Arch §11.
- Keyboard navigable with visible focus.
- Text meets AA contrast.
- No console errors.
- `pnpm build` passes.

---

## F8 — News Agent

**Objective:** A near-real-time crypto news feed, tagged with tracked symbols.

**Flow:** Every 15 min:

1. Fetch RSS sources (and CryptoPanic if a key is set).
2. Normalise and deduplicate by URL.
3. Tag symbols: whole-word, case-sensitive match on the base coin (minimum 3 characters, skipping the stoplist in `news_sources.yaml`). Match against active contracts only.
4. Insert new items.
5. `NOTIFY news_new`.

**Business rules:**

- One failing source sets the run to `PARTIAL`; the run continues.
- Store only title, URL, source and time. No article bodies.

**Acceptance:** The news panel updates, and failed sources appear in the run meta.

---

## F9 — Signal Agent (Phase 4, gated)

**Objective:** BUY / SELL / trend-change status on 5m, 15m and 1h for selected and pinned symbols, from the FGI Replica V3 port.

**Flow:** Every 5 min:

1. Fetch closed klines for 5m, 15m, 1h and 4h.
2. Compute the indicators (Arch §7, `skills/pine-port.md`).
3. Upsert `signals` and insert new `signal_events`.
4. `NOTIFY signal_new`.

**UI (middle panel, above the movers):** one card per symbol with three timeframe rows. Each row shows:

- M trend
- last event and bars ago (✗ if against the 4H trend)
- consolidated trend
- SuperTrends
- grades
- divergence
- s/r letter
- zone position

**Acceptance:**

- The parity check passes the tolerance in `skills/pine-port.md`.
- No signal is generated on a forming bar.

---

## F10 — Telegram Alerts (Phase 5, gated)

**Objective:** Push new BUY / SELL / BULL_T / BEAR_T events to Telegram.

**Business rules:**

- Send exactly once per `signal_events` row.
- Rate-limit sends.
- Never include secrets.
- Message contents: symbol, timeframe, event, against-HTF tag, price, bar close time (IST); no disclaimer text (removed 2026-10-06).

**Acceptance:** A test message is delivered, and each event is delivered exactly once.

---

## F11 — Data retention & operations

**Objective:** Keep storage bounded and the host healthy.

**Requirements:**

- A daily purge removes rows older than `RETENTION_DAYS` (5). It keeps at least `kline.backfill_bars` per symbol in `klines_15m`.
- `/api/status` reports the DB size.
- All services use `restart: unless-stopped`.
- Memory limits: worker 1 GB, api 512 MB, web 512 MB, db 1 GB.

**Acceptance:** After a purge, no time-series row is older than 5 days (except the kline floor), and the DB size is visible.

---

## F12 — Market Movers (UTC day)

**Objective:** Top 10 gainers and top 10 losers since 00:00 UTC among liquid contracts.

**Flow:** After every snapshot (5 min):

1. Compute `utc_day_change_pct` (Arch §5.6).
2. Rank the results.
3. Persist `market_movers`.
4. `NOTIFY movers_updated`.

**Business rules:**

- Liquid contracts only. Nothing is excluded by asset type, so BTC and ETH can appear.
- A symbol without today's open is skipped.
- Show the `WAITING_DAY_OPEN` state immediately after 00:00 UTC, until the first daily open is recorded.
- IST is used for display only.

**Acceptance:** `/api/movers/latest` returns 10 + 10 rows that refresh every 5 min, and the UI list sits below the signals section.
