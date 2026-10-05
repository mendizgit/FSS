# MEMORY — TSS progress (single file · edit changed lines only · max 150 lines)

updated: 2026-10-05 | commit: 75fcc30 | phase: P1 | status: AWAITING_REVIEW

## Next step
- P1 complete + validated (ER §12). Waiting for user review and "commit" (P1 commit not made; P0 = 75fcc30). Decisions needed: zero_fee refresh cadence, Float vs numeric prices, startup preflight wording. Next phase P2 (F6 live ticker, F7 dashboard) only after user types "start P2" - plan first.

## Features (TODO / WIP / DONE / BLOCKED)
F0 DONE · F1 DONE · F2 DONE · F3 DONE · F4 DONE · F5 DONE · F6 TODO · F7 TODO · F8 TODO · F9 BLOCKED(gated) · F10 BLOCKED(gated) · F11 DONE · F12 DONE(data)

## Blockers / questions for user
- none

## Log (newest first · max 10 lines · delete oldest)
- 2026-10-05 P1 phase-end validation passed: ruff/mypy/pip-audit clean, pytest 29, simulate_failures 47/47, alembic check clean, preflight 27/0, web lint/type/build ok, secrets scan clean, Docker stack ran scheduled :05 and :15:20 ticks; zero_fee flag is volatile on MEXC (70..507 within the hour)
- 2026-10-05 P1 built: clients(http/futures/spot), domain(5 mods, 29 unit checks), repos, agents(universe/snapshot/kline_sync/momentum/classification/movers/retention), control(breaker/health/pipeline/scheduler), API routes, scripts/simulate_failures.py (36 checks pass); live run natively + in Docker ok; BTC 1h metrics hand-verified vs raw MEXC
- 2026-10-05 P0 phase-end validation passed: ruff/mypy/pip-audit clean, alembic fresh temp DB up/check/down/up ok, preflight 27/0 fail, web lint/type/build ok, secrets scan clean, stack healthy on :8088 w/ auth+headers; fixed 2 ValueError->ValidationError; pnpm audit (dev) 1 high: braces via eslint-config-next, no patch; pytest: no tests yet (none required until domain/)
- 2026-10-05 full stack up (project tss): db/api/web healthy, worker up, proxy on <LAN_IP>:8088 (8080 taken by vidhive uvicorn); 401 w/o creds ok, db/api/web not reachable on LAN; docs+CHANGELOG updated for 8088; authenticated 200 + headers verified (hash reset by user request)
- 2026-10-05 P0 step 6 done: backend/web Dockerfiles, docker-compose.yml (name: tss), Caddyfile (validated), api /api/health + worker skeleton; images built; api health 200 db ok, web 200, worker alembic ok; NOT run: full stack (BASIC_AUTH_HASH still placeholder)
- 2026-10-05 P0 step 5 done: web/ Next 16.3.8 + React 19 + Tailwind 4, TS strict, output standalone; pnpm lint/type-check/build pass, audit clean; state codes confirmed from MEXC docs
- 2026-10-05 P0 step 4 done: scripts/preflight.py 27 checks, 0 failed, 3 to review (state meaning, kline cap 2000, forming bar included); ruff+mypy clean; Arch §3.1/§4 + CHANGELOG v1.3.1 edited (time unit seconds, state codes confirmed from MEXC docs)
- 2026-10-05 P0 step 3 done: models match Arch §9; migration cdfd7a420a08 (plain sa.DateTime(tz)); upgrade/downgrade/upgrade ok, `alembic check` clean, 0 naive timestamps, 5 indexes; ruff+mypy clean; tss-db-dev running (volume tss_pgdata_dev)
- 2026-10-05 reconcile after crash: step 3 partially on disk (db/ models+session, alembic env, docker-compose.dev.yml; NO migration, db not started); .env has all .env.example names
- 2026-10-05 P0 step 2 done: uv project, core/{errors,time,logging,settings}, config/*.yaml; ruff+mypy clean; config-failure/redaction checks pass

## Decisions & API quirks (one line each)
- MEXC detail zero-fee fields flicker between calls (507, 507, 451 within a minute; our 6 h refresh once caught 70); badge is display-only
- P1 decisions: pool_rank for pinned outside the pool = position in full RVOL ranking (>50), no row if RVOL unknown; 'active' contracts = state 0 + not denylisted + in latest universe refresh (updated_at == max); WARMING_UP system state while earliest snapshot < 4h old; TF_CONFLICT = bullish(LONG_BUILDUP,SHORT_COVERING) vs bearish(SHORT_BUILDUP,LONG_UNWINDING); kline gap check uses newest 2n bars; HTTP retries = 3 after first attempt (2/4/8 s + jitter)
- MEXC payloads: futures ticker numerics are numbers, spot ticker numerics are strings, spot kline row = [openMs,o,h,l,c,vol,closeMs,quoteVol] (ms), futures kline time in s, futures kline amount = USDT turnover; detail has isZeroFeeRate flags (not used; zero_fee = both fee rates == 0 per Arch §4)
- LAN port 8088 (host) -> Caddy :8080 in container; 8080 is used by another local app (vidhive)
- Web deps deferred to P2: shadcn/ui (components.json), TanStack Query, lucide-react; no Google fonts (system font, offline-safe builds)
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
- backend/scripts/preflight.py — public MEXC/RSS/WS checks, prints table (exit 1 on any ✗)
- backend/config/{thresholds,denylist,news_sources}.yaml — Arch §13 values (RSS URLs proposed, verify in preflight)

## Env (tool versions · verified commands · last validation)
- 2026-10-05 host: git 2.43.0 · uv 0.12.23 · sys python 3.12.3 (uv-visible, not used for project) · node 22.23.2 (nvm) · pnpm 12.9.1 · docker 29.8.2 · compose 5.6.0 · user in docker group, daemon reachable
- Resolved: fastapi 0.142.2 · pydantic 2.13.5 · sqlalchemy 2.1.3 · uvicorn 0.54.0 · httpx 0.28.1 · websockets 17.2 · structlog 26.1.0 · venv py 3.12.3 (system 3.12 base)
- Verified: uv run ruff check/format, mypy src (strict) clean
