# Skill — Local LAN Deployment & GitHub Readiness

## Role

Prepare and run TSS on the Ubuntu host with Docker Compose, reachable only from the operator's Windows PC on the same LAN.

## Targets

- Dev: `docker-compose.dev.yml` (db only); backend and web run natively.
- Runtime: `docker-compose.yml` with services `db`, `worker`, `api`, `web`, `proxy`.
- **No cloud deployment.** Vercel, Render and similar are out of scope.

## Compose rules

- Only `proxy` publishes a port: `8088:8080` (host 8088 → Caddy :8080 inside the container). `db`, `api` and `web` stay on the internal network.
- `restart: unless-stopped` on all services. Memory limits are set per FEATURE_BLUEPRINT F11.
- Healthchecks:
  - db: `pg_isready`
  - api: `/api/health`
  - web: HTTP 200 on `/`
- `worker` and `api` depend on db being healthy. `worker` runs `alembic upgrade head` before starting the scheduler.
- Persist the Postgres data in a named volume. **Never** run `down -v` without user approval.
- Python image: `python:3.12-slim` + uv. Web image: multi-stage Node LTS with Next.js `output: 'standalone'`. Both run as non-root users.

## Caddy

- Listen on `:8080`.
- Routes:
  - `/api/*` and `/ws` → `api:8000`
  - everything else → `web:3000`
- `basic_auth` on all routes with a bcrypt hash from env (`caddy hash-password`).
- Security headers: CSP (`default-src 'self'; connect-src 'self' ws: wss:; img-src 'self' data:`), `X-Frame-Options DENY`, `Referrer-Policy no-referrer`, `X-Content-Type-Options nosniff`.
- No TLS. This is plain HTTP on a trusted LAN; document it as a known limitation.

## LAN access (document; the user executes)

```bash
sudo ufw allow from <LAN_CLIENT_IP> to any port 8088 proto tcp
sudo ufw deny 8088/tcp
sudo ufw status numbered
```

- The Windows PC opens `http://<ubuntu-lan-ip>:8088`.
- Recommend a DHCP reservation for both machines so the IPs stay fixed.
- Docker can bypass ufw for published ports. Mitigate by binding the published port to the LAN interface IP (`<UBUNTU_LAN_IP>:8088:8080`) and documenting the `DOCKER-USER` chain rule if needed. Do not run these commands; provide them.

## Environment variables

- Keep `.env.example` complete with placeholders only. `.env` must be mode 600 and gitignored.
- Never commit, print or log secret values.

## GitHub readiness

Before any push the user requests:

- secrets scan of staged files
- `.gitignore` covers `.env`, `.venv`, `node_modules`, `.next`, `__pycache__`, DB dumps and logs
- README sections: overview, architecture diagram, prerequisites (Docker, uv, Node LTS, pnpm), setup, preflight, dev run, production run, LAN access, env vars, troubleshooting, disclaimer
- the remote must be **private**

## Operations notes (README)

- Start/stop: `docker compose up -d` / `docker compose stop`
- Logs: `docker compose logs -f worker`
- Status: `http://<ip>:8088` status bar or `/api/status`
- Data: auto-purged after `RETENTION_DAYS`
- Update: `git pull && docker compose up -d --build`

## Final delivery

Provide a concise run checklist. Never claim a deployment succeeded unless it was executed and `curl /api/health` returned 200.
