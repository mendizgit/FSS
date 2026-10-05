"""Telegram Bot API client (Phase 5). Official API: https://core.telegram.org/bots/api

The bot token is part of the request URL, so this client NEVER logs, raises or stores a URL,
and never puts exception text into an error: only the HTTP status, Telegram's own
`description` and the exception class name. Messages are plain text (no parse_mode).
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from pydantic import SecretStr

from tss.core.errors import DataSourceError

COMPONENT = "telegram"
PHASE = "P5"
API_BASE = "https://api.telegram.org"
TIMEOUT = httpx.Timeout(10.0, connect=5.0)
MAX_TEXT = 4096

# httpx logs full request URLs at INFO; keep that out of every log sink.
for _name in ("httpx", "httpcore"):
    logging.getLogger(_name).setLevel(logging.WARNING)


class TelegramError(DataSourceError):
    """Base for Telegram failures. `permanent` errors need a human (bad token / chat)."""

    permanent = False


class TelegramRateLimited(TelegramError):
    def __init__(self, operation: str, retry_after: float) -> None:
        super().__init__(
            COMPONENT,
            PHASE,
            operation,
            f"rate limited by Telegram (retry after {retry_after:g} s)",
            {"retry_after": retry_after},
        )
        self.retry_after = retry_after


class TelegramPermanentError(TelegramError):
    permanent = True


class TelegramClient:
    def __init__(
        self,
        token: SecretStr,
        chat_id: str,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._token = token
        self.chat_id = chat_id
        self._client = client or httpx.AsyncClient(timeout=TIMEOUT)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _call(self, method: str, payload: dict[str, Any]) -> Any:
        url = f"{API_BASE}/bot{self._token.get_secret_value()}/{method}"
        try:
            resp = await self._client.post(url, json=payload)
        except httpx.HTTPError as exc:  # never include str(exc): it can carry the URL
            raise TelegramError(
                COMPONENT, PHASE, method, f"network error ({type(exc).__name__})"
            ) from None
        try:
            body = resp.json()
        except ValueError:
            body = {}
        if resp.status_code == 200 and isinstance(body, dict) and body.get("ok") is True:
            return body.get("result")
        description = (
            str(body.get("description", "no description")) if isinstance(body, dict) else ""
        )
        description = description.replace(self._token.get_secret_value(), "***")
        if resp.status_code == 429:
            params = body.get("parameters", {}) if isinstance(body, dict) else {}
            retry = params.get("retry_after") if isinstance(params, dict) else None
            raise TelegramRateLimited(
                method, float(retry) if isinstance(retry, int | float) else 30.0
            )
        message = f"HTTP {resp.status_code}: {description}"
        if resp.status_code in (400, 401, 403, 404):
            raise TelegramPermanentError(
                COMPONENT, PHASE, method, message, {"status": resp.status_code}
            )
        raise TelegramError(COMPONENT, PHASE, method, message, {"status": resp.status_code})

    async def send_message(self, text: str) -> None:
        await self._call(
            "sendMessage",
            {
                "chat_id": self.chat_id,
                "text": text[:MAX_TEXT],
                "link_preview_options": {"is_disabled": True},
            },
        )

    async def get_me(self) -> dict[str, Any]:
        result = await self._call("getMe", {})
        return result if isinstance(result, dict) else {}

    async def get_updates(self) -> list[dict[str, Any]]:
        result = await self._call("getUpdates", {"timeout": 0, "limit": 100})
        return result if isinstance(result, list) else []
