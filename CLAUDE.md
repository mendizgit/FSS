# CLAUDE.md — Trading Signal System (TSS)

MEXC USDT-perpetual market analysis platform (**MEXC is the only market-data source**). Runs locally on an Ubuntu host and is viewed from a Windows PC on the same LAN. **Analysis only — no trading.**

## Memory & context loading (token-saving)

- `agent-kit/MEMORY.md` is the **single memory file**. It is injected automatically at session start, together with a git summary.
- Do **not** read the whole agent-kit each session. Use `agent-kit/INDEX.md` to load only the doc sections the current feature needs.
- Find code via the `Code map` section in MEMORY.md before searching the tree.
- Update MEMORY.md with **small in-place edits** after each completed step and before asking for approval. Use `/save`, or the same rules manually.
- A `⚠ DRIFT` warning means commits exist after the last memory update. Fix the MEMORY header first.

Source of truth: the `agent-kit/` documents. On the first session only, or when unsure, read `PROJECT_GUIDELINES.md` and `EXECUTION_RULES.md` in full. If documents conflict with each other or with the repository, stop and ask the user.

## Hard rules (summary; full text in `agent-kit/`)

- **Never** place orders, call private or trading endpoints, manage positions, or give personalised investment advice.
- **Never** print, log, echo, or commit secrets. Do not `cat` `.env`. Do not print settings objects.
- **Never** invent data fields. If a source does not return a field, store it as `unavailable` and report the gap to the user.
- **Never** scrape a site when an official public endpoint exists.
- Work **one phase at a time**. Stop at the end of each phase and wait for user review.
- Store all timestamps in **UTC**. Display them in **IST** (`Asia/Kolkata`, UTC+05:30).
- Every error message must name the **component, phase, and operation**.
- Ask before any destructive action: deleting volumes or data, dropping tables, force-pushing, or deleting branches.

## Working agreement (user + Claude Code only; no external reviewer)

**Session start**
- Use injected MEMORY.md; on ⚠ DRIFT reconcile MEMORY.md first. Load only INDEX.md-listed sections for the current feature. First session only: read PROJECT_GUIDELINES.md + EXECUTION_RULES.md in full.

**Phase workflow** (order P0 → P1 → P2 → P3; P4/P5 only on user typing "start P4" / "start P5")
- Plan (≤ 15 lines: features, files, commands, risks) → wait for "approved".
- Implement feature by feature. After each: run its validation, update MEMORY.md (/save rules), status ≤ 8 lines, ask "continue?". On "run phase autonomously" continue to phase end, but still stop on any blocker or stop-and-ask item.
- Phase end: full validation (EXECUTION_RULES §12), summary (§17), MEMORY status AWAITING_REVIEW, proposed commit message. Commit only when user types "commit".

**Self-review**
- After the P0 preflight, compare against every ⚠ item in SYSTEM_ARCHITECTURE §3 and the kline/WS assumptions in §5. Table: item | expected | actual | impact | proposed doc change. No architecture-doc edits until approved; then update docs + CHANGELOG in the same commit.
- Before closing a phase check: blueprint acceptance conditions, no secrets in code/logs/git, error format (component/phase/op), UTC storage / IST display, closed bars only, no private or trading endpoints.

**Stop and ask when**
- any EXECUTION_RULES §16 item; docs vs actual API/schema mismatch; any threshold change; any architecture-affecting choice; anything needed from the user (.env values, installs, ufw/sudo commands).

**Secrets**
- User creates .env from .env.example. Tell them which variable names to fill and how to generate values (e.g. Caddy bcrypt hash). Never read/cat/print .env.

**Communication**
- Concise, technical, bullets, no preamble/recap. Numbered questions at the end. When user must run commands: one step at a time, wait for output before the next.

## Environment

- **Python**: project-local venv `backend/.venv` managed by uv; Python 3.12 pinned in `backend/.python-version`. Use `uv add` / `uv sync` / `uv run` only. Never `pip install` globally, never `sudo pip`, never use system Python for the project.
- **Node**: pnpm, deps in `web/node_modules`; Node LTS pinned in `web/.nvmrc`, plus `engines` and `packageManager` in `web/package.json`.
- **VS Code**: `.vscode/settings.json` sets `python.defaultInterpreterPath` to `backend/.venv/bin/python`.
- **Production**: Docker images built from the same `uv.lock` / `pnpm-lock.yaml` (identical dependencies).
- Tool versions are recorded in MEMORY.md `Env`.
- Never run sudo, firewall, or system-level commands. Give the user the exact commands and wait for their output.

## Commands

The commands below are created in Phase 0. Keep this section in sync if they change.

```bash
# Infrastructure (dev: database only; app runs natively)
docker compose -f docker-compose.dev.yml up -d db

# Backend
cd backend
uv sync
uv run alembic upgrade head
uv run python scripts/preflight.py          # MEXC endpoint/field + news source checks
uv run ruff check . && uv run ruff format --check .
uv run mypy src
uv run pytest                               # calculation/indicator checks only
uv run python -m tss.entrypoints.worker     # agents + scheduler
uv run uvicorn tss.entrypoints.api:app --host 127.0.0.1 --port 8000

# Web
cd web
pnpm install
pnpm dev
pnpm lint && pnpm type-check && pnpm build

# Full stack (LAN)
docker compose up -d --build
```
