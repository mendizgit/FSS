"""Message text and Telegram client behaviour (F10). No network: httpx MockTransport."""

import asyncio
import json
import logging
from datetime import UTC, datetime

import httpx
import pytest
from pydantic import SecretStr

from tss.clients.telegram import (
    MAX_TEXT,
    TelegramClient,
    TelegramError,
    TelegramPermanentError,
    TelegramRateLimited,
)
from tss.domain.notifier import DISCLAIMER, connectivity_message, format_event_message, format_price

TOKEN = "123456:SECRET-TOKEN-VALUE"
CLOSE = datetime(2026, 10, 5, 10, 5, 0, tzinfo=UTC)  # 15:35:00 IST
SNAP = datetime(2026, 10, 5, 10, 0, 0, tzinfo=UTC)  # 15:30:00 IST


def msg(**kw: object) -> str:
    base: dict[str, object] = {
        "symbol": "BTC_USDT",
        "timeframe": "5m",
        "event": "BUY",
        "against_htf": True,
        "price": 85913.4,
        "price_time": SNAP,
        "bar_close_time": CLOSE,
    }
    return format_event_message(**{**base, **kw})  # type: ignore[arg-type]


def test_message_text_is_exact() -> None:
    assert msg() == (
        "▲ BUY · BTC_USDT · 5m\n"
        "Bar closed: 2026-10-05 15:35:00 IST\n"
        "Last price: 85,913.40 (snapshot 2026-10-05 15:30:00 IST)\n"
        "✗ Against the 4H trend\n"
        "Market analysis only. Not financial advice."
    )


def test_message_variants() -> None:
    assert "✓ With the 4H trend" in msg(against_htf=False)
    text = msg(against_htf=None, event="BEAR_T", price=None, price_time=None)
    assert text.startswith("▼ bearT · BTC_USDT · 5m") and "Last price: unavailable" in text
    assert "4H trend" not in text
    assert all(DISCLAIMER in m for m in (msg(), text, connectivity_message()))


def test_price_formatting() -> None:
    assert format_price(0.0001234) == "0.0001234"
    assert format_price(2.5) == "2.5000"
    assert format_price(1234.5) == "1,234.50"
    assert format_price(None) == "unavailable"


def make_client(handler) -> TelegramClient:  # type: ignore[no-untyped-def]
    return TelegramClient(
        SecretStr(TOKEN), "42", client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )


def test_send_message_request_shape() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

    asyncio.run(make_client(handler).send_message("hello"))
    assert seen["path"] == f"/bot{TOKEN}/sendMessage"
    body = seen["body"]
    assert isinstance(body, dict)
    assert body["chat_id"] == "42" and body["text"] == "hello"
    assert "parse_mode" not in body  # plain text: titles can never inject markup
    assert body["link_preview_options"] == {"is_disabled": True}


def test_text_is_capped() -> None:
    captured: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(len(json.loads(request.content)["text"]))
        return httpx.Response(200, json={"ok": True, "result": {}})

    asyncio.run(make_client(handler).send_message("x" * 10_000))
    assert captured == [MAX_TEXT]


def test_error_classification() -> None:
    def respond(status: int, body: dict[str, object]):  # type: ignore[no-untyped-def]
        return lambda r: httpx.Response(status, json=body)

    with pytest.raises(TelegramRateLimited) as rl:
        asyncio.run(
            make_client(
                respond(
                    429,
                    {
                        "ok": False,
                        "error_code": 429,
                        "description": "Too Many Requests: retry after 7",
                        "parameters": {"retry_after": 7},
                    },
                )
            ).send_message("x")
        )
    assert rl.value.retry_after == 7
    with pytest.raises(TelegramPermanentError):
        asyncio.run(
            make_client(respond(401, {"ok": False, "description": "Unauthorized"})).send_message(
                "x"
            )
        )
    with pytest.raises(TelegramPermanentError):
        asyncio.run(
            make_client(respond(400, {"ok": False, "description": "chat not found"})).send_message(
                "x"
            )
        )
    with pytest.raises(TelegramError) as server:
        asyncio.run(make_client(respond(502, {})).send_message("x"))
    assert not server.value.permanent  # 5xx is transient: the agent retries
    assert server.value.component == "telegram" and server.value.phase == "P5"


def test_token_never_leaks(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    echo = {"ok": False, "description": f"Unauthorized (token {TOKEN} rejected)"}

    def leaky_network(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"failed to reach {request.url}")  # message carries the URL

    errors: list[TelegramError] = []
    for handler in (lambda r: httpx.Response(401, json=echo), leaky_network):
        with pytest.raises(TelegramError) as exc:
            asyncio.run(make_client(handler).send_message("x"))
        errors.append(exc.value)
    for err in errors:
        dump = f"{err} | {err!r} | {err.message} | {err.context} | {err.__cause__}"
        assert TOKEN not in dump and "SECRET-TOKEN-VALUE" not in dump
        assert "api.telegram.org" not in dump
    assert errors[0].message.endswith("Unauthorized (token *** rejected)")
    assert "network error (ConnectError)" in errors[1].message
    assert TOKEN not in caplog.text
