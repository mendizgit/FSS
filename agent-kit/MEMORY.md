# MEMORY — TSS progress (single file · edit changed lines only · max 150 lines)

updated: 2026-10-07 | commit: fc4e9c2 (+uncommitted: pool-wide signals, setup alerts, dashboard Pause/Start, +5 s cron) | phase: P5 | status: AWAITING_REVIEW

## Next step
- Code deployed in Docker (uncommitted on branch feat/heikin-ashi; user must type "commit"). System is PAUSED (daily 00:00-06:00 IST) until the user presses "Start system" in the header; Telegram is still PAUSED (header button). After Start verify: signal run duration with ~80 pool symbols, +5 s timing (bar final?), baseline run records current setups without alerts, then new Long/Short setups alert once. Open: SETUP_MAX_AGE 10 min (user asked what it means; may raise), TV parity (F9), STOCK-symbol TradingView names (only MRVL confirmed), coin-name news tagging, CryptoPanic, zero_fee cadence.

## Features (TODO / WIP / DONE / BLOCKED)
F0 DONE · F1 DONE · F2 DONE · F3 DONE · F4 DONE · F5 DONE · F6 DONE · F7 DONE(news/signals = module-off placeholders) · F8 DONE · F9 BUILT(parity UNPROVEN) · F10 DONE(live) · F11 DONE · F12 DONE(data)

## Blockers / questions for user
- ALERT LATENCY: resolved 2026-10-06 (signal job runs right after each pipeline + every 5 min at +20 s; alert drops older than the freshness window). Observe live.

## Log (newest first · max 10 lines · delete oldest)
- 2026-10-07 user-approved: signals evaluate WHOLE movers pool (live_symbols = non-pinned pool + majors); signal cron */5 at +5 s; domain/setups.py (Long/Short rule, shared by API `setup` + alerts, 4H informational only); agents/setup.py + table signal_setups (migration d8f3a6b2c914) + notifier now sends ONE alert per NEW setup (replaces raw event alerts, SETUP_MAX_AGE 10 min, baseline on first run, majors not alerted; message has `4H trend : ✓ With|✗ Against|—`); dashboard Pause/Start: POST /api/control/run, flag `run` in control_flags (Pause until next 06:00 IST, Start until next 00:00 IST), control/schedule.pause_state, worker pause_watch 10 s catch-up, status.pause; ruff/mypy clean, pytest 89, sims pass (signals 35, telegram 31, failures 64, ticker 17, news 27); NOT committed
- 2026-10-06 back to NORMAL candles (pipeline.py uses agents/signal.py; HA files kept); scheduler signal cron minute=*/5 +20 s (pipeline still runs it after saving selection); deleted 505 unsent signal_events since 04:21 UTC (28 notified kept as duplicate guard); /api/signals/latest rows now carry recent_events (BUY/SELL/BULL_T/BEAR_T, 11 h, newest event merged in); web Signals tabs Longs/Shorts/Majors (neutral dropped; Long = 5m<=5b or 15m<=2b BUY/bullT + 1h bullish event <=10b, both M trend Up; Short mirror), fresh badge, with/against 4H; Classification hides symbols NEUTRAL in 1h and 4h; symbol name opens TradingView MEXC:BASEUSDT.P (STOCK suffix dropped); MEXC probe pause committed 4122d77, TV link e5d2c9f/5bd3f18; pytest 77, sims pass
- 2026-10-06 MEXC probe pause (branch feat/heikin-ashi, UNCOMMITTED, not in Docker): futures.ping() (/api/v1/contract/ping, 1 attempt), Controller._mexc_reachable gate (2 failed probes => mexc_down => universe/snapshot/movers/pipeline/signal skipped, news keeps running, system_state HALTED w/ MEXC reason, no migration), mexc_recovery_job every 15 s resumes + snapshot/pipeline/signal catch-up; kline_sync stops after 5 consecutive connect failures; simulate_failures 58/58 (scenario 1b), other sims + pytest 77 pass
- 2026-10-06 HA signals (branch feat/heikin-ashi, UNCOMMITTED, not in Docker yet): indicators/heikin_ashi.py + agents/signal_ha.py wired in pipeline.py; old agents/signal.py kept for rollback; ruff/mypy clean, pytest 77, simulate_signals 25 + telegram 30 pass; TD alerts removed from Telegram (NOTIFY_EVENTS = BUY/SELL/BULL_T/BEAR_T)
- 2026-10-06 zone_position restored (column+API+GUI, migration c5a2d7e91f08) committed b3c40ba; telegram TD/5m+15m/bar-close committed as 6d6feb4
- 2026-10-06 signals cleanup: dropped 10 derived columns (migration b3e8f01c6d44) + API/GUI/SignalSnapshot; kept m_trend/last_event/bars_ago/against_htf/price_vs_vwap; sim_config disables quiet hours so sims are clock-independent; pytest 75, all sims pass
- 2026-10-06 persistent flags: control_flags table + migration 7a1d3c9e5b20, control/flags.py, api/routes/flags.py (POST /api/flags/{news|telegram}), status.flags, header buttons; worker builds Telegram client whenever creds exist, notifier gated per run by flag (flag overrides TELEGRAM_ALERTS env; no row = env); pytest 75, sims pass (telegram 30)
- 2026-10-05 user: universe also pauses in quiet hours (cron universe_resume 06:00 IST); top_n 20->30; News panel toggle in status bar (localStorage tss-news-open), wider Signals column when hidden
- 2026-10-05 quiet_hours config (pause 0 / resume 6 IST) gates snapshot/movers/pipeline/signal/news in Controller._exclusive (control/pipeline.py, schedule.in_quiet_hours); status route reports PAUSED; web chip; tests/test_schedule_quiet.py; pytest 72, sims pass (run outside window)
- 2026-10-05 user-approved: pool 80 / RVOL>=1.2 / |d15m|>=0.8% (top_n 20), signals exclude pinned (majors kept), signal job runs after each pipeline (cron every 5 min at +20 s, skips :00/:15/:30/:45); ruff/mypy/pytest 70, sims pass (signals 25, failures 47, ticker 17, telegram 29); NOT yet restarted in Docker/committed

## Decisions & API quirks (one line each)
- MEXC detail zero-fee fields flicker between calls (507, 507, 451 within a minute; our 6 h refresh once caught 70); badge is display-only
- Realtime facts: prices tick ~1/s via MEXC WS for every shown symbol; panels refresh on backend events (no polling, 60 s fallback); analysis is computed on closed bars (snapshots/signals 5 min, classification/news 15 min) by design (no forming-bar signals). docker-compose backend env must list every new env var (TELEGRAM_* were missing until 2026-10-05)
- Alert pause switch: TELEGRAM_ALERTS=on|off in .env (non-secret); off keeps token/chat id, notifier not run, events stay unnotified and are only sent on resume if still within freshness window (5m 15 min, 15m 30 min, 1h 2 h)
- P5 decisions: events pushed = BUY/SELL/BULL_T/BEAR_T (TD_BULL/TD_BEAR pushed 2026-10-06 only, removed again same day by user); pushed timeframes 5m+15m only (2026-10-06); freshness windows 5m 15min / 15m 30min (older events never sent); claim-then-send (at-most-once; a crash between claim and send loses that alert, never duplicates); release on any send failure; ~1.1 s between messages, max 20 per run, 429 retry_after<=30 s waits once else releases; alert format (user-specified 2026-10-05): bold `BASEUSDT.P`, `Time : 5 min|15 min`, `Bar close : HH:MM IST` (added 2026-10-06), `Signal : 🟢 Buy|🔴 Sell|—`, `Trend : BullT|BearT`, no disclaimer footer (removed 2026-10-06); `✗ Against the 4H trend` line only when true; HTML parse mode, all values escaped; no price in the message; Telegram runs only when both env values non-empty
- Signals/UI decisions (2026-10-06): MEXC futures has NO Min3 kline (Min1/5/15/60 ok), a 3m series would need aggregating 1m bars (not built); MEXC probe = GET /api/v1/contract/ping (2 failed probes pause MEXC jobs, news unaffected, state HALTED, resume probe every 15 s); signal_events store only the 3 newest bars per run so recent_events history is partial; TradingView link = MEXC:BASEUSDT.P, BASESTOCK_USDT -> BASEUSDT.P; Pause/Start semantics: manual Pause expires at next 06:00 IST, manual Start at next 00:00 IST, then daily schedule; "12:00 AM" = 00:00 IST
- P4 decisions: ASSUMPTION to confirm via parity: ta.pivothigh/low centre strictly beyond the left bars, >= / <= the right bars (plateau => first bar); HTF (4H SuperTrend, 1H/4H RSI) = last CLOSED HTF bar at each bar close (documented deviation); ST direction + RSI are not plotted by the Pine script so parity compares plots only (R/S/M, EMAs, VWAP, events, s/r letters); rsi_divergence = regular divergence on the newest closed bar only (POS_REG/NEG_REG); zone_position labels TOP_SUB/TOP_MAIN/MID/BOTTOM_MAIN/BOTTOM_SUB; against_htf only for BUY/SELL/BULL_T/BEAR_T (TD = NULL); events scanned on the newest 3 bars, unique key keeps inserts idempotent; min 500 bars per signal TF and 100 per HTF series else skipped with a reason; single-pivot divergence flag (confluence factor 5) stays on while its pivot condition holds, then decays 20 bars (as Pine); VWAP anchored to UTC day using kline `vol`
- P3 decisions: news tagged by TICKER only (whole-word, case-sensitive, >=3 chars, active contracts, stoplist in news_sources.yaml); headlines usually say 'Bitcoin' not 'BTC' so many items are untagged (contract detail has baseCoinName; using it = rule change, needs approval); CryptoPanic NOT implemented: API docs unreachable, endpoint/terms unverified, and no key set; items w/ implausible future date get published_at NULL; old (>5d) items skipped; NOTIFY payloads over 7000 B are shrunk to {truncated:true}; feeds are fetched with follow_redirects
- P2 decisions: ws events are the primary refresh trigger (60 s fallback poll), ticks only feed price store; /ws served by api process (hub + LISTEN tss_events + MEXC ticker gateway for selected+pinned); dev needs API_ORIGIN + NEXT_PUBLIC_WS_URL; layout cols 1.75/1.4/0.55 at >=1280; News/Signals panels are placeholders (F8 = P3, F9 = P4); no keepPreviousData on window toggle (avoids mislabelled numbers)
- P1 decisions: pool_rank for pinned outside the pool = position in full RVOL ranking (>50), no row if RVOL unknown; 'active' contracts = state 0 + not denylisted + in latest universe refresh (updated_at == max); WARMING_UP system state while earliest snapshot < 4h old; TF_CONFLICT = bullish(LONG_BUILDUP,SHORT_COVERING) vs bearish(SHORT_BUILDUP,LONG_UNWINDING); kline gap check uses newest 2n bars; HTTP retries = 3 after first attempt (2/4/8 s + jitter)
- MEXC payloads: futures ticker numerics are numbers, spot ticker numerics are strings, spot kline row = [openMs,o,h,l,c,vol,closeMs,quoteVol] (ms), futures kline time in s, futures kline amount = USDT turnover; detail has isZeroFeeRate flags (not used; zero_fee = both fee rates == 0 per Arch §4)
- LAN port 8088 (host) -> Caddy :8080 in container; 8080 is used by another local app (vidhive)
- Web: shadcn (base-nova, Base UI primitives: use `render` prop, not asChild), TanStack Query 5, lucide-react, clsx+tailwind-merge; shadcn CLI pkg is a devDependency; fonts Inter+JetBrains Mono via next/font/google (needs network at build); `cn` npm pkg from shadcn registry was replaced by src/lib/utils.ts
- Contract state (MEXC docs): 0 enabled, 1 delivery, 2 delivered, 3 offline, 4 paused; universe = USDT/USDT and state==0
- Preflight 2026-10-05: futures kline max 2000 bars/call, time in seconds, last bar can be the forming one (drop it); detail state=0 for all 1186 contracts; fees returned (488 zero-fee); WS push.ticker + pong ok; 4 RSS ok; ~158 liquid
- Approved extra deps beyond Arch §2: PyYAML (config loading), pip-audit (dev; Arch §12); types-pyyaml (mypy stubs for PyYAML)
- Deferred deps (add when needed): apscheduler (F5), pandas/numpy (F3+)
- Config dir override: TSS_CONFIG_DIR; default backend/config

## Code map (one line per module: path — purpose)
- .gitignore, .env.example (placeholders), README.md (skeleton), .vscode/settings.json — repo hygiene
- backend/.python-version (3.12), web/.nvmrc (22) — runtime pins
- backend/pyproject.toml, uv.lock — deps + ruff/mypy(strict, pydantic plugin)/pytest config
- backend/src/tss/core/errors.py — TSSError + DataSource/Validation/Calculation/Config/Storage
- backend/src/tss/core/time.py — utc_now, floor_to_minutes, next_boundary, utc_day_*, format_ist
- backend/src/tss/core/logging.py — structlog JSON, redaction, bind_context
- backend/src/tss/core/settings.py — Settings (env, SecretStr) + YAML models; load_config / load_config_or_exit (exit 78)
- backend/src/tss/db/{base,session}.py, db/models/* (10 tables: contracts, market_snapshots, klines_15m, daily_opens, market_movers, momentum_rankings, classifications, news_items, agent_runs, system_state), backend/alembic/{env.py,versions/cdfd7a420a08_initial_schema.py}, alembic.ini, docker-compose.dev.yml — step 3
- web/ — Next.js skeleton (src/app/{layout,page,globals.css}), scripts: lint, type-check (typegen+tsc), build
- backend/src/tss/{api/app.py,entrypoints/{api,worker}.py} — /api/health + worker skeleton; backend/Dockerfile, web/Dockerfile, docker-compose.yml, Caddyfile — step 6
- backend/src/tss/clients/{http,models,mexc_futures,mexc_spot}.py — HttpClient (retry/limiter), typed payloads, MEXC REST clients
- backend/src/tss/domain/{calculations,universe,momentum,movers,classification}.py — pure rules (tests/test_*.py)
- backend/src/tss/db/repositories/{contracts,market,discovery,ops}.py — all SQL
- backend/src/tss/agents/{base,common,universe,snapshot,kline_sync,momentum,classification,movers,retention}.py — F1-F4,F11,F12
- backend/src/tss/control/{breaker,health,pipeline,schedule,scheduler}.py — Controller (F5), APScheduler jobs
- backend/src/tss/api/{app,deps}.py, api/routes/*, api/schemas/models.py — /api status, universe/summary, discovery, classification, movers, config
- backend/scripts/simulate_failures.py — F5/F11 acceptance (throwaway DB tss_sim)
- backend/src/tss/realtime/{hub,notify,ticker_gateway,symbols}.py, api/ws.py — event hub, LISTEN loop, MEXC WS gateway (F6), /ws
- backend/scripts/simulate_ticker.py — F6 acceptance (fake MEXC WS server)
- web/src/{lib,hooks,types}/ — api-client, ws-client, price-store, time (IST only here), format, query hooks; web/src/features/{status-bar,classification,movers,signals,news}/; components/{layout,tss,ui}
- backend/src/tss/clients/rss.py, domain/news.py, agents/news.py, db/repositories/news.py, api/routes/news.py — F8 (feeds -> news_items -> /api/news); web/src/features/news/news-panel.tsx
- backend/scripts/simulate_news.py — F8 acceptance (throwaway DB)
- backend/src/tss/indicators/{primitives,range_filter,supertrend,divergence,zones,fgi_v3}.py — Pine port (MPL-2.0 headers on range_filter/divergence); agents/signal.py, db/models/signals.py, db/repositories/signals.py, api/routes/signals.py; web/src/features/signals/*
- backend/src/tss/{indicators/heikin_ashi,agents/signal_ha}.py — HA variant, NOT active (rollback: swap import in control/pipeline.py)
- backend/scripts/{simulate_signals,parity_check}.py, backend/tests/{test_indicator_primitives,test_indicators}.py, tests/fixtures/tv/README.md
- backend/src/tss/clients/telegram.py, domain/notifier.py, agents/notifier.py, db/repositories/signals.py (claim_events/release_events); backend/scripts/{telegram_setup,simulate_telegram}.py; tests/test_notifier.py
- backend/src/tss/{domain/setups,agents/setup}.py, db/models/signals.py (SignalSetup), db/repositories/signals.py (load_views/claim_setups/release_setups); control/schedule.py (pause_state), api/routes/flags.py (/control/run); tests/test_setups.py
- backend/scripts/preflight.py — public MEXC/RSS/WS checks, prints table (exit 1 on any ✗)
- backend/config/{thresholds,denylist,news_sources}.yaml — Arch §13 values (RSS URLs proposed, verify in preflight)

## Env (tool versions · verified commands · last validation)
- 2026-10-05 host: git 2.43.0 · uv 0.12.23 · sys python 3.12.3 (uv-visible, not used for project) · node 22.23.2 (nvm) · pnpm 12.9.1 · docker 29.8.2 · compose 5.6.0 · user in docker group, daemon reachable
- Resolved: fastapi 0.142.2 · pydantic 2.13.5 · sqlalchemy 2.1.3 · uvicorn 0.54.0 · httpx 0.28.1 · websockets 17.2 · structlog 26.1.0 · venv py 3.12.3 (system 3.12 base)
- Verified: uv run ruff check/format, mypy src (strict) clean
