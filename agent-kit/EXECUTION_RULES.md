# Execution Rules — Trading Signal System (TSS)

## 1. Start with context

At the start of every session:

1. Use the injected `MEMORY.md` and git summary from the SessionStart hook. If they are missing, read `agent-kit/MEMORY.md`.
2. Load only the sections listed in `INDEX.md` for the current feature.
3. Use the MEMORY.md `Code map` to locate code. Open specific files only. Do not scan the whole tree.
4. Read full documents only on the first session, when a rule is unclear, or when the task spans the whole system.

## 2. Phase gating

- Work only on the phase the user names.
- Before writing code, show a short plan of the files to create or change, and wait for approval when the plan affects more than one feature.
- At phase end, update MEMORY.md (`status: AWAITING_REVIEW`), give the chat summary in §17 format, and **stop**. Do not start the next phase until the user says so.
- P4 (Signal engine) and P5 (Telegram) need an explicit user go-ahead.

## 3. Map the request

For every task, map:

```text
Requirement → Feature (F#) → Data source → Client → Domain logic → Agent → Repository/Table
→ API endpoint → WS event → UI panel/component → Config keys → Files
```

If any link cannot be mapped from the agent-kit documents, ask the user.

## 4. Use the right skill

| Work | Skill |
|---|---|
| External APIs, agents, scheduling, calculations | `skills/market-data-agents.md` |
| FastAPI, DB, repositories | `skills/backend.md` |
| Pine → Python port (P4) | `skills/pine-port.md` |
| API ↔ UI data flow, WebSocket | `skills/integration.md` |
| React/Next.js code | `skills/frontend.md` |
| Layout, visual design, states | `skills/ui-design.md` |
| Docker, Caddy, LAN, ufw, GitHub | `skills/deployment.md` |

Do not apply unrelated skills.

## 5. Inspect before edit

Never blindly replace files. Read the current implementation and preserve unrelated work. Use targeted edits instead of full rewrites.

## 6. Implement incrementally

Make the smallest complete change that satisfies the requirement. No speculative features, and no features from later phases.

## 7. Missing data / mismatch handling

If a document says a field or endpoint exists but the live API or schema does not provide it:

- do **not** invent the field, a substitute value, or an alternative source
- store `NULL` and record an `unavailable` reason where the design allows it (e.g. `spot_volume_change_pct` → `no_spot_market`)
- report exactly what is missing (endpoint, field, observed response shape, with no secrets)
- ask whether the architecture, blueprint, source or data model should change

If the documents already define a fallback for that case, apply it and report it.

## 8. External API rules

- Use official public endpoints only. No scraping and no unofficial mirrors. No private or trading endpoints, ever.
- Before using an endpoint marked ⚠ in the architecture, confirm it in `scripts/preflight.py` output.
- All HTTP goes through `clients/http.py`:
  - timeouts: connect 5 s, read 15 s
  - retry policy per Arch §8
  - per-host rate limiter
  - honour `Retry-After`
- MEXC is the **only** market-data source. Do not add another market-data provider (CMC, CoinGecko, Binance, etc.) without user approval.
- Prefer batch endpoints (all-symbol ticker) over per-symbol loops. Fetch klines incrementally from the stored `klines_15m` table, not a full history every cycle.
- Save sanitised sample payloads into `backend/tests/fixtures/` for calculation checks. Strip headers and keys.

## 9. Secrets

- Read secrets only through `core/settings.py` (`SecretStr`).
- Never print, log or return secrets, `.env` contents or full settings objects. Do not run `cat .env`, `env` or `printenv` in the terminal.
- When a secret is missing, error with the variable **name** only.
- Before every commit, check that no secret patterns are staged (`git diff --cached`).

## 10. Error handling format

Every raised or logged error carries `component`, `phase`, `operation` and a human-readable message. Example:

```text
[TSS] component=mexc_futures_client phase=snapshot op=GET /api/v1/contract/ticker
      error=HTTP 429 rate limited — retry 2/3 in 4.0s
```

- Agent failures are written to `agent_runs.error_*` and surfaced in the status bar.
- The API returns `{error:{code,message,component}}` with no stack traces.
- Unexpected exceptions are wrapped in `TSSError` at the agent boundary. Never swallow an exception silently.

## 11. UI-first quality

Every UI feature must have:

- correct layout per Arch §11
- consistent tokens
- responsive behaviour
- keyboard access
- loading, empty, warming-up, stale and error states

Colour is never the only carrier of meaning.

## 12. Validation (run before each phase report)

```bash
# backend
uv run ruff check . && uv run ruff format --check .
uv run mypy src
uv run pytest                     # calculation / classification / parity checks only
uv run alembic upgrade head       # on a fresh dev DB
uv run python scripts/preflight.py
# web
pnpm lint && pnpm type-check && pnpm build
# runtime smoke
docker compose up -d --build && curl -fsS localhost:8088/api/health   # with basic auth
```

- Unit checks are required **only** for `domain/` and `indicators/` (approved exception). There is no broader test suite.
- Report exactly which commands ran and their results. Never claim comprehensive testing.

## 13. Local-first development

- Dev: DB in Docker (`docker-compose.dev.yml`); backend and web run natively with `uv` and `pnpm`.
- API dev bind is `127.0.0.1:8000`; web dev bind is `127.0.0.1:3000`.
- Use the VS Code Remote-SSH port forward for viewing during dev.
- Keep dev and production config separate (`.env`, compose files).

## 14. Git / GitHub readiness

- Run `git init` in P0. Make one focused commit per approved step, using Conventional Commits (`feat(p1): …`).
- Before any push: secrets check, `.gitignore` verified, `.env.example` updated, README updated.
- The GitHub remote, if used, must be **private**. Never push without the user's instruction.

## 15. Deployment

- The target is Docker Compose on the Ubuntu host, exposed on the LAN via Caddy (host port 8088) only (see `skills/deployment.md`).
- No cloud deployment (Vercel, Render or others) is in scope.
- Provide the `ufw` commands but **do not run** firewall or sudo commands. The user runs them.

## 16. Ask before

- deleting files outside the current feature
- `docker compose down -v`, dropping tables, `TRUNCATE`, or rewriting migrations already applied
- adding a dependency not listed in Arch §2
- changing a threshold value in `config/thresholds.yaml`
- any `sudo`, firewall, or system-level change
- `git push`, force-push, or deleting branches

## 17. Phase-end summary (in chat, not a file)

Keep it to 15 lines or fewer, under these headings:

- **Changed** — files, grouped by feature
- **Decisions** — assumptions made
- **Validation** — commands run and their results
- **Data-source findings**
- **Open issues / questions for the user**

Copy only the durable facts into MEMORY.md.

## 18. Communication

Be concise. For each completed step, report what changed, the files, decisions, the validation run, and unresolved issues. Do not write long explanations unless asked.

## 19. Memory protocol (single file: `agent-kit/MEMORY.md`)

| Section | Content | Rule |
|---|---|---|
| Header | updated, commit, phase, status | Edit on every save |
| Next step | One line, executable with no chat history | Replace |
| Features | Status codes on one line | Change only the codes that moved |
| Blockers / questions | Open items | Remove when resolved |
| Log | One line per completed step, newest first | Keep at most 10; delete the oldest |
| Decisions & API quirks | One line each | Append only when new |
| Code map | `path — purpose`, one line per module | Edit when files are added, moved or removed |
| Env | Tool versions, verified commands, last validation | Replace lines |

- **When to save:** after each completed step, before asking for approval, and before `/clear`. Do not save after reads or questions.
- **How to save:** use targeted edits. Never rewrite the whole file. Keep it to 150 lines or fewer.
- **What to save:** facts only. No secrets, no `.env` values, no logs.
- MEMORY.md is committed together with the code it describes.
- Architecture-level changes go to `SYSTEM_ARCHITECTURE.md`, with user approval.
