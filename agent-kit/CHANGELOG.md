# Agent Kit Changelog

## v1.3.1 — 2026-10-05 (P0 preflight findings)
- Arch §3.1: kline `time` is in seconds; the last bar returned can be the forming one (drop it, per §5.2).
- LAN port: host/LAN port is now 8088 (8080 is used by another local app). Caddy still listens on :8080 inside its container; compose maps `<UBUNTU_LAN_IP>:8088:8080`. Updated Arch §2/§12 text, ER §12/§16, skills/deployment.md, README.
- Arch §4: `state` codes confirmed from MEXC docs (0 enabled, 1 delivery, 2 delivered, 3 offline, 4 paused); universe filter uses `state == 0`.

## v1.3 — 2026-10-05
- Simplified memory to a **single file**, `agent-kit/MEMORY.md`, updated by in-place edits.
- Removed: `memory/` folder (STATE, JOURNAL, HISTORY, CODEMAP, DECISIONS), `reports/`, the Stop hook, `/resume`, `/checkpoint`, `/phase-close`.
- Kept: the SessionStart hook (injects MEMORY.md and git status, with a drift check), `INDEX.md`, and one command, `/save`.
- Phase-end reports are now a short chat summary (EXECUTION_RULES §17).

## v1.2 — 2026-10-05
- Memory system added: `agent-kit/memory/` (STATE, JOURNAL, HISTORY, CODEMAP, DECISIONS).
- `agent-kit/INDEX.md` maps each feature to the doc sections it needs, so docs are loaded by section rather than in full.
- `.claude/` additions:
  - SessionStart hook injects STATE + git summary and flags drift.
  - Stop hook reminds Claude to checkpoint.
  - New slash commands: `/resume`, `/checkpoint`, `/phase-close`.
- CLAUDE.md and EXECUTION_RULES §1 now use the context-loading protocol. EXECUTION_RULES gains §19 Memory protocol.

## v1.1 — 2026-10-05
- MEXC is now the only market-data source. CMC was removed from the architecture, blueprint, env, tables and preflight.
- Liquidity gate: 24h turnover ≥ $1M and OI notional ≥ $500k. This replaces the market-cap filter.
- Discovery funnel: liquid universe → top 50 movers pool by RVOL → Gate 2 (|Δp 15m| ≥ 1.5 % and RVOL ≥ 1.5×) → top 20.
- Nothing is excluded by asset type. BTC_USDT and ETH_USDT are pinned as market context.
- New F12 Market Movers: top 10 gainers and losers since 00:00 UTC, shown below the Signals panel.
- New tables: `klines_15m`, `daily_opens`, `momentum_rankings`, `market_movers`.
- Removed tables: `cmc_assets`, `momentum_selections`.
- Out of scope: order flow, footprint, CVD, order book.
- Zero-fee badge added (display only, if MEXC returns fee fields).

## v1.0 — 2026-10-05
- Initial approved kit (CMC + MEXC).
