# Trading Signal System (TSS)

MEXC USDT-perpetual market analysis dashboard. Runs locally on an Ubuntu host, viewed from a Windows PC on the same LAN.

> Market analysis only — not financial advice. The system never places orders or calls private/trading endpoints.

## Architecture
_TODO (diagram) — see `agent-kit/SYSTEM_ARCHITECTURE.md`._

## Prerequisites
- Docker + Docker Compose
- uv (Python 3.12 is managed per project in `backend/.venv`)
- Node.js LTS (see `web/.nvmrc`) and pnpm

## Setup
```bash
cp .env.example .env && chmod 600 .env   # then fill in the placeholders
```

## Preflight
```bash
cd backend && uv run python scripts/preflight.py
```

## Development run
```bash
docker compose -f docker-compose.dev.yml up -d db
cd backend && uv sync && uv run alembic upgrade head
uv run python -m tss.entrypoints.worker
uv run uvicorn tss.entrypoints.api:app --host 127.0.0.1 --port 8000
cd web && pnpm install && API_ORIGIN=http://127.0.0.1:8000 NEXT_PUBLIC_WS_URL=ws://127.0.0.1:8000/ws pnpm dev
```
In dev, `API_ORIGIN` proxies `/api` to the local API; the browser connects to `/ws` directly through `NEXT_PUBLIC_WS_URL` (Next does not proxy WebSockets). In production Caddy routes `/api/*` and `/ws` to the api service, so neither variable is set.

## Production run
```bash
docker compose up -d --build        # project name: tss (separate from the dev stack)
docker compose ps                   # db/api/web should be healthy
```
- Only `proxy` publishes a port: `${UBUNTU_LAN_IP}:8088`. `db`, `api` and `web` stay on the internal network.
- `worker` runs `alembic upgrade head` before starting.
- Never run `docker compose down -v` (it deletes the `tss_pgdata` volume).
- `BASIC_AUTH_HASH` is a bcrypt hash containing `$`. Wrap it in **single quotes** in `.env` so compose does not interpolate it:
  `docker run --rm caddy:2 caddy hash-password --plaintext '<password>'`, then `BASIC_AUTH_HASH='<hash>'`.
- `POSTGRES_PASSWORD` is embedded in `DATABASE_URL`; avoid characters that need URL-encoding (`@ : / ? # %`).

## LAN access
Open `http://<UBUNTU_LAN_IP>:8088` from the Windows PC (basic auth). Plain HTTP on a trusted LAN is a known limitation.
Firewall (run by the operator, not by the tooling):
```bash
sudo ufw allow from <LAN_CLIENT_IP> to any port 8088 proto tcp
sudo ufw deny 8088/tcp
sudo ufw status numbered
```
Docker can bypass ufw for published ports; the port is therefore bound to `UBUNTU_LAN_IP` only (see `agent-kit/skills/deployment.md` for the `DOCKER-USER` note). Use DHCP reservations so both IPs stay fixed.

## Environment variables
See `.env.example` (placeholders only). Thresholds live in `backend/config/*.yaml`.

## Troubleshooting
- Config error on start: exit code 78 and a `[TSS] component=settings` message naming the bad key/file.
- `/api/health` returns 503: the database is unreachable (`docker compose ps`, check `db` health).
- `.env` values with spaces: quote them; compose and shell parse them differently.

## Disclaimer
Market analysis only — not financial advice. Plain HTTP on a trusted LAN (no TLS) is a known limitation.
