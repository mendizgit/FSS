# Project Guidelines — Trading Signal System (TSS)

## Purpose

TSS is a local, LAN-only crypto market analysis platform. It does the following:

1. Builds a liquid universe of MEXC USDT perpetual contracts (MEXC is the single data source).
2. Every 15 minutes, ranks a top-50 movers pool by relative volume and selects up to 20 momentum candidates. BTC and ETH are always tracked as market context.
3. Lists the top 10 gainers and top 10 losers of the UTC day.
4. Classifies each candidate's derivatives state (price / open interest / volume / funding).
5. (Phase 4) Generates technical signals from a Python port of the Pine indicator `FGI Replica V3`.
6. Shows status, classification, signals, movers and news on a real-time web dashboard.
7. (Phase 5) Forwards signals to Telegram.

The system is **analysis only**. It never trades.

## Source-of-truth documents

1. `SYSTEM_ARCHITECTURE.md` — how the system is built.
2. `FEATURE_BLUEPRINT.md` — what the system must do, by phase.
3. `PROJECT_STRUCTURE.md` — where code belongs.
4. `EXECUTION_RULES.md` — how work is carried out.

The agent's job is to execute this plan. It must not redesign it.

## Execution priority

1. Explicit user instruction (latest wins)
2. System architecture
3. Feature blueprint
4. Project structure
5. Existing code and conventions
6. Engineering best practices

## Core rules

- Inspect existing code before changing it.
- Reuse existing modules, utilities and patterns.
- Keep changes limited to the current phase and feature.
- Do not rewrite unrelated code.
- Do not add a framework or library unless `SYSTEM_ARCHITECTURE.md` lists it or the user approves it.
- Do not invent requirements, endpoints, database fields, thresholds or business rules.
- Do not silently change the architecture.
- Prefer simple, maintainable implementations.
- Python: type hints everywhere, `mypy`-clean, Pydantic models at boundaries.
- TypeScript: strict mode, no unnecessary `any`.
- Separate concerns: clients (I/O) → domain (pure calculations) → agents (orchestration) → repositories (DB) → API.
- All thresholds and tunables live in `backend/config/*.yaml`. No magic numbers in code.
- Handle loading, empty, error, stale and warming-up states in the UI.
- Build responsive, accessible interfaces from the start.

## Domain rules (non-negotiable)

- **No trading.** Use only public market-data endpoints. Never call order, position, account or transfer endpoints.
- **No personalised advice.** The UI shows a persistent notice: "Market analysis only — not financial advice."
- **Single source = MEXC.** Identity is the MEXC futures contract symbol (`BASE_USDT`). No CMC or other market-data provider.
- **Nothing is excluded by asset type.** BTC and ETH are tracked. Only the liquidity gate filters contracts, plus an optional manual denylist that is empty by default.
- **Simple scope:** order flow, footprint, CVD and order-book analysis are out of scope.
- **Missing data is never fabricated.** A field the source does not return is stored as `NULL` with an `unavailable` reason, then surfaced to the user.
- **UTC storage, IST display.**
- **Closed bars only** for signal calculations. A forming candle must never produce a signal.
- **Secrets** are read only from environment variables. They never appear in logs, errors, API responses or the UI.

## Missing information rule

Stop and ask the user when a missing or conflicting requirement materially affects implementation. Examples:

- A data source does not return a field that the blueprint requires.
- An external endpoint behaves differently from `SYSTEM_ARCHITECTURE.md` (path, fields, limits).
- A threshold is needed but not defined in config.
- Two requirements conflict.

Do not ask about minor details that a reasonable implementation choice can resolve. Record such assumptions in the phase report.

## Validation rule

There is no formal QA phase. Run the lightweight validation listed in `EXECUTION_RULES.md` §12.

**Exception (approved):** numeric correctness cannot be verified visually, so these targeted checks are required:

- unit checks for calculation and classification functions
- the Pine parity check for the signal engine (Phase 4)

Never claim the application is "fully tested".

## Development and runtime target

- Development: Claude Code on the Ubuntu host (`~/Documents/Development/trading-signal-system`).
- Runtime: Docker Compose on the same Ubuntu host.
- Access: browser on a Windows PC on the same LAN only. No public exposure and no cloud deployment.
- Repository: Git, with an optional **private** GitHub remote.

## Delivery standard

The completed application must be:

- functional and integrated end-to-end
- visually polished, data-dense, responsive and accessible (WCAG 2.2 AA where practical)
- resilient: degrades with stale indicators instead of crashing
- configurable through `.env` and `config/*.yaml`
- runnable locally with documented commands
- organised for Git
- not indexed by search engines (`noindex`; SEO is out of scope because the app is private)

## Git rules

- Never commit secrets. Keep `.gitignore` and `.env.example` current.
- Make one focused commit per completed, user-approved step.
- Do not delete or overwrite unrelated user work.
- Keep `README.md` and `CLAUDE.md` aligned with the actual commands.

## Completion rule

A feature is complete only when its full data flow works:

source → agent → DB → API → UI

The UI existing on its own does not make a feature complete.
