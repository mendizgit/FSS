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
from tss.domain.notifier import (
    NOTIFY_EVENTS,
    connectivity_message,
    display_symbol,
    format_event_message,
)

TOKEN = "123456:SECRET-TOKEN-VALUE"


def msg(**kw: object) -> str:
    base: dict[str, object] = {
        "symbol": "UMA_USDT",
        "timeframe": "5m",
        "event": "BUY",
        "against_htf": False,
        "bar_close_time": datetime(2026, 10, 6, 9, 5, tzinfo=UTC),  # 14:35 IST
    }
    return format_event_message(**{**base, **kw})  # type: ignore[arg-type]


def test_buy_message_is_exact() -> None:
    assert msg() == (
        "<b>UMAUSDT.P</b>\nTime : 5 min\nBar close : 14:35 IST\nSignal : 🟢 Buy\nTrend : BullT"
    )


def test_sell_and_trend_only_variants() -> None:
    sell = msg(event="SELL", timeframe="15m", symbol="BTC_USDT")
    assert sell.splitlines()[:5] == [
        "<b>BTCUSDT.P</b>",
        "Time : 15 min",
        "Bar close : 14:35 IST",
        "Signal : 🔴 Sell",
        "Trend : BearT",
    ]
    bull_only = msg(event="BULL_T", timeframe="1h")
    assert (
        "Time : 1 hour" in bull_only and "Signal : —" in bull_only and "Trend : BullT" in bull_only
    )
    assert "TD_BULL" not in NOTIFY_EVENTS and "TD_BEAR" not in NOTIFY_EVENTS
    bear_only = msg(event="BEAR_T")
    assert "Signal : —" in bear_only and "Trend : BearT" in bear_only


def test_against_4h_marker_and_escaping() -> None:
    assert msg(against_htf=True).endswith("\n<i>✗ Against the 4H trend</i>")
    assert "financial advice" not in msg(against_htf=True) and "financial advice" not in msg()
    assert "✗" not in msg(against_htf=None) and "✗" not in msg(against_htf=False)
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
