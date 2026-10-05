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

## Telegram alerts (Phase 5)
Optional. New **BUY / SELL / bullT / bearT / TD** signal events (5m and 15m only) are pushed to one Telegram chat, exactly once each, rate-limited (about 1 message/s), only while they are fresh (5m: 15 min, 15m: 30 min, 1h: 2 h old at most). Alerts look like this (HTML, symbol in bold):
```
UMAUSDT.P
Time : 5 min
Bar close : 14:35 IST
Signal : 🟢 Buy          (🔴 Sell; "—" for a trend flip or TD without a BUY/SELL signal)
Trend : BullT            (BearT; "TD Bull" / "TD Bear")
✗ Against the 4H trend   (only when the event goes against the 4H trend)
```
1. In Telegram, talk to **@BotFather**, create a bot and put its token in `.env` as `TELEGRAM_BOT_TOKEN`.
2. Open your new bot and send it `/start`.
3. `cd backend && uv run python scripts/telegram_setup.py discover` prints your chat id; put it in `.env` as `TELEGRAM_CHAT_ID`.
4. `uv run python scripts/telegram_setup.py test` sends a test message (`sample` sends one alert in the format above).
5. `docker compose up -d worker` (restart so the worker picks up `.env`). The dashboard's Telegram chip turns on.

**Pause / resume:** set `TELEGRAM_ALERTS=off` in `.env` (then `docker compose up -d worker api`) to stop alerts without removing the token and chat id; set it back to `on` to resume. Events that are still fresh when you resume (5m: 15 min, 15m: 30 min, 1h: 2 h) are sent; older ones are skipped.

Delivery is claim-then-send: an event is marked notified before it is sent and released again if sending fails, so it is never duplicated; a crash between those two steps can lose that one alert.

## Environment variables
See `.env.example` (placeholders only). Thresholds live in `backend/config/*.yaml`.

## Troubleshooting
- Config error on start: exit code 78 and a `[TSS] component=settings` message naming the bad key/file.
- `/api/health` returns 503: the database is unreachable (`docker compose ps`, check `db` health).
- `.env` values with spaces: quote them; compose and shell parse them differently.

## Disclaimer
Market analysis only — not financial advice. Plain HTTP on a trusted LAN (no TLS) is a known limitation.
