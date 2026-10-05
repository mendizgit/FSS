# INDEX — what to read for each task

Read **only** the sections listed for the current feature. Do not read whole documents unless the task spans the whole system.
Locate a section with: `grep -n "^## <n>\." agent-kit/SYSTEM_ARCHITECTURE.md`, then read that range.

Abbreviations: Arch = `SYSTEM_ARCHITECTURE.md`, BP = `FEATURE_BLUEPRINT.md`, ER = `EXECUTION_RULES.md`, sk = `skills/`

## Always loaded (automatically)
- `CLAUDE.md`
- `MEMORY.md` (injected by the SessionStart hook)

## Per feature

| Feature | BP | Arch sections | Skills |
|---|---|---|---|
| F0 Foundation | F0 | §2, §9, §12, §13 | sk/backend, sk/deployment |
| F1 Universe | F1 | §3.1, §4, §9 (`contracts`) | sk/market-data-agents |
| F2 Snapshots | F2 | §3.1–3.2, §4 (liquidity), §5.1, §9 | sk/market-data-agents |
| F3 Kline/Pool/Selection | F3 | §5.2–5.4, §8, §9 | sk/market-data-agents |
| F4 Classification | F4 | §3.2, §5.5, §6, §9 | sk/market-data-agents |
| F5 Control | F5 | §8 | sk/market-data-agents, sk/backend |
| F6 Live ticker | F6 | §3.1 (WS), §10 | sk/integration |
| F7 Dashboard | F7 | §10, §11 | sk/frontend, sk/ui-design, sk/integration |
| F8 News | F8 | §3.3, §9 (`news_items`) | sk/market-data-agents |
| F9 Signals (gated) | F9 | §7, §9 (`signals`) | sk/pine-port + `reference/pine/fgi_replica_v3.pine` |
| F10 Telegram (gated) | F10 | §3.4 | sk/backend |
| F11 Retention/ops | F11 | §9, §12 | sk/deployment |
| F12 Movers | F12 | §5.2 (daily_opens), §5.6, §10, §11 | sk/market-data-agents, sk/ui-design |

## Read only when needed
- `PROJECT_GUIDELINES.md` — on the first session, or when a rule question arises.
- `PROJECT_STRUCTURE.md` — when creating a new file or folder. Use the MEMORY.md `Code map` to find existing code.
- `EXECUTION_RULES.md` — §2 (gating), §7 (missing data), §12 (validation), §16 (ask-before), §19 (memory) as relevant.
- `reference/pine/` — Phase 4 only.
