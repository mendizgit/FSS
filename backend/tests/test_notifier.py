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
from tss.domain.notifier import connectivity_message, display_symbol, format_setup_message

TOKEN = "123456:SECRET-TOKEN-VALUE"


def msg(**kw: object) -> str:
    base: dict[str, object] = {
        "symbol": "UMA_USDT",
        "bias": "long",
        "trigger_timeframe": "5m",
        "trigger_event": "BUY",
        "htf_event": "BULL_T",
        "htf_bars_ago": 3,
        "trigger_bar_close_time": datetime(2026, 10, 6, 9, 5, tzinfo=UTC),  # 14:35 IST
        "against_htf": False,
    }
    return format_setup_message(**{**base, **kw})  # type: ignore[arg-type]


def test_long_message_is_exact() -> None:
    assert msg() == (
        "<b>UMAUSDT.P</b>\nSetup : 🟢 Long\nTrigger : 5 min Buy\n"
        "1h confirm : BullT, 3 bars ago\nBar close : 14:35 IST\n4H trend : ✓ With"
    )


def test_short_variant_and_ago_wording() -> None:
    short = msg(
        symbol="BTC_USDT",
        bias="short",
        trigger_timeframe="15m",
        trigger_event="BEAR_T",
        htf_event="SELL",
        htf_bars_ago=1,
    )
    assert short.splitlines() == [
        "<b>BTCUSDT.P</b>",
        "Setup : 🔴 Short",
        "Trigger : 15 min BearT",
        "1h confirm : Sell, 1 bar ago",
        "Bar close : 14:35 IST",
        "4H trend : ✓ With",
    ]
    assert "1h confirm : BullT, now" in msg(htf_bars_ago=0)


def test_4h_line_is_informational_and_escaping() -> None:
    assert msg(against_htf=True).endswith("4H trend : ✗ Against")
    assert msg(against_htf=None).endswith("4H trend : —")
    assert "financial advice" not in msg(against_htf=True)
    weird = msg(symbol="A<b>&_USDT")
    assert "<b>A&lt;b&gt;&amp;USDT.P</b>" in weird  # symbols are escaped, markup cannot be injected


def test_display_symbol() -> None:
    assert display_symbol("BTC_USDT") == "BTCUSDT.P"
    assert display_symbol("1000PEPE_USDT") == "1000PEPEUSDT.P"
    assert "financial advice" not in connectivity_message()


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
    plain = seen["body"]
    asyncio.run(make_client(handler).send_message("<b>x</b>", html=True))
    assert isinstance(plain, dict) and "parse_mode" not in plain
    assert isinstance(seen["body"], dict) and seen["body"]["parse_mode"] == "HTML"
    asyncio.run(make_client(handler).send_message("hello"))
    assert seen["path"] == f"/bot{TOKEN}/sendMessage"
    body = seen["body"]
    assert isinstance(body, dict)
    assert body["chat_id"] == "42" and body["text"] == "hello"
    assert "parse_mode" not in body  # plain by default; HTML only for our own escaped markup
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
