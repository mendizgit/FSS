# Project Structure — Trading Signal System (TSS)

Repository root: `~/Documents/Development/trading-signal-system`

Place new code in the matching module below. Do not create arbitrary folders.

## Approved structure

```text
trading-signal-system/
├── CLAUDE.md                      # Claude Code entry point (auto-loaded)
├── .claude/
│   ├── settings.json              # SessionStart hook (injects MEMORY.md)
│   ├── hooks/session-start.sh
│   └── commands/save.md           # /save → update MEMORY.md
├── README.md
├── .env.example                   # placeholders only
├── .gitignore
├── docker-compose.yml             # production: db, worker, api, web, proxy
├── docker-compose.dev.yml         # dev: db only
├── Caddyfile
├── agent-kit/
│   ├── PROJECT_GUIDELINES.md
│   ├── SYSTEM_ARCHITECTURE.md
│   ├── FEATURE_BLUEPRINT.md
│   ├── PROJECT_STRUCTURE.md
│   ├── EXECUTION_RULES.md
│   ├── INDEX.md                   # feature → doc sections to load
│   ├── CHANGELOG.md
│   ├── MEMORY.md                  # single progress memory file
│   ├── skills/                    # frontend, ui-design, backend, integration, deployment,
│   │                              # market-data-agents, pine-port
│   └── reference/pine/fgi_replica_v3.pine
├── backend/
│   ├── pyproject.toml / uv.lock
│   ├── Dockerfile
│   ├── alembic.ini
│   ├── alembic/versions/
│   ├── config/                    # thresholds.yaml, denylist.yaml, news_sources.yaml
│   ├── scripts/
│   │   ├── preflight.py
│   │   └── parity_check.py        # P4
│   ├── tests/                     # calculation, classification, indicator parity only
│   │   └── fixtures/              # recorded API payloads, TradingView CSV exports
│   └── src/tss/
│       ├── core/                  # settings, logging (+redaction), errors, time
│       ├── db/
│       │   ├── base.py, session.py
│       │   ├── models/            # SQLAlchemy models, one file per aggregate
│       │   └── repositories/      # all SQL lives here
│       ├── clients/               # external I/O only, no business logic
│       │   ├── http.py            # shared httpx client, retry, rate limiter
│       │   ├── mexc_futures.py
│       │   ├── mexc_spot.py
│       │   ├── mexc_ws.py
│       │   ├── rss.py
│       │   ├── cryptopanic.py
│       │   └── telegram.py        # P5
│       ├── domain/                # pure functions, no I/O
│       │   ├── universe.py        # contract filtering, liquidity gate, zero-fee, pinned
│       │   ├── calculations.py    # pct_change, rvol, window metrics
│       │   ├── momentum.py        # movers pool, gate 2, ranking
│       │   ├── movers.py          # UTC-day gainers / losers
│       │   └── classification.py  # states + flags
│       ├── indicators/            # P4: Pine port (pure pandas/numpy)
│       │   ├── primitives.py      # ema, rma, sma, stdev, atr, rsi, pivots, bb, vwap
│       │   ├── range_filter.py
│       │   ├── supertrend.py
│       │   ├── divergence.py
│       │   ├── zones.py
│       │   └── fgi_v3.py          # composes everything → signal row
│       ├── agents/                # orchestration: fetch → domain → repo
│       │   ├── base.py            # BaseAgent: run lifecycle, error capture
│       │   ├── universe.py
│       │   ├── snapshot.py
│       │   ├── kline_sync.py
│       │   ├── movers.py
│       │   ├── momentum.py
│       │   ├── classification.py
│       │   ├── news.py
│       │   ├── signal.py          # P4
│       │   ├── notifier.py        # P5
│       │   └── retention.py
│       ├── control/
│       │   ├── scheduler.py       # APScheduler jobs
│       │   ├── pipeline.py        # cycle_id, dependencies
│       │   ├── breaker.py
│       │   └── health.py          # system_state
│       ├── realtime/
│       │   ├── events.py          # event schemas
│       │   ├── notify.py          # pg NOTIFY / LISTEN
│       │   └── ticker_gateway.py  # MEXC WS → /ws fan-out
│       ├── api/
│       │   ├── app.py             # FastAPI factory, error handlers
│       │   ├── routes/            # status, discovery, universe, classification, movers, signals, news, config
│       │   ├── ws.py
│       │   └── schemas/           # Pydantic response models
│       └── entrypoints/
│           ├── worker.py
│           └── api.py
└── web/
    ├── package.json / pnpm-lock.yaml
    ├── Dockerfile
    ├── next.config.ts             # output: 'standalone'
    ├── components.json            # shadcn
    └── src/
        ├── app/                   # layout.tsx, page.tsx, globals.css (tokens)
        ├── components/
        │   ├── ui/                # shadcn primitives only
        │   └── layout/            # dashboard grid, panel shell, header, footer notice
        ├── features/
        │   ├── status-bar/
        │   ├── classification/
        │   ├── signals/
        │   ├── movers/            # gainers / losers lists (rendered below signals)
        │   └── news/
        ├── hooks/                 # useWebSocket, useLiveTicker, useAgentStatus
        ├── lib/                   # api-client.ts, ws-client.ts, time.ts (IST), format.ts, query-client.ts
        └── types/                 # api.ts (mirrors backend schemas), events.ts
```

## Folder responsibilities

- `clients/` — HTTP/WS calls, response parsing into Pydantic models, rate limiting. No thresholds, no DB.
- `domain/` and `indicators/` — deterministic, pure functions. No I/O, no clock reads (time is passed in). These are the only modules with unit checks.
- `agents/` — call clients, then domain functions, then repositories. They own run status and error capture.
- `control/` — scheduling, dependencies, breakers, system state. It does not compute business logic.
- `db/repositories/` — the only place SQL or ORM queries appear.
- `api/` — thin routes delegating to repositories. Only response schemas cross the boundary.
- `realtime/` — event definitions and transport only.
- `web/src/features/<x>/` — the components, hooks and formatters of one panel. Shared pieces go to `components/`, `hooks/` or `lib/`.

## Naming conventions

- Python: `snake_case` modules and functions, `PascalCase` classes, enums as `StrEnum`.
- TypeScript: `kebab-case.tsx` files, `PascalCase` components, `camelCase` functions.
- DB: `snake_case` plural table names; timestamps are `*_at` or `ts`.
- Symbols: futures `BASE_USDT`, spot `BASEUSDT`. Both are stored explicitly; the code never derives one from the other at query time.

## Placement rule

Before creating a file:

1. Check whether an appropriate module already exists.
2. Reuse existing patterns.
3. Place the file according to this structure.
4. Do not create a new architectural layer for a small feature. New top-level folders require user approval.
