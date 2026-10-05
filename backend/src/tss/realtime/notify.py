"""LISTEN tss_events: the api process turns Postgres NOTIFY into hub events (Arch §8, §10)."""

from __future__ import annotations

import asyncio
import json
import random
from typing import Any

import asyncpg  # type: ignore[import-untyped]
from sqlalchemy.engine import make_url

from tss.core.logging import get_logger
from tss.db.repositories.ops import CHANNEL
from tss.realtime.hub import EventHub

COMPONENT = "realtime"
BACKOFF_S = (1.0, 2.0, 4.0, 8.0, 15.0, 30.0)


def asyncpg_dsn(sqlalchemy_url: str) -> str:
    return (
        make_url(sqlalchemy_url).set(drivername="postgresql").render_as_string(hide_password=False)
    )


async def listen_loop(dsn: str, hub: EventHub) -> None:
    """Reconnects forever. Malformed payloads are logged and skipped, never fatal."""
    log = get_logger(COMPONENT)
    attempt = 0
    while True:
        conn: Any = None
        try:
            conn = await asyncpg.connect(dsn)
            attempt = 0

            def on_notify(_c: Any, _pid: int, _channel: str, payload: str) -> None:
                try:
                    event = json.loads(payload)
                except ValueError:
                    log.warning("bad NOTIFY payload", component=COMPONENT, phase="P2", op="listen")
                    return
                if isinstance(event, dict) and "type" in event:
                    hub.publish(event)

            await conn.add_listener(CHANNEL, on_notify)
            log.info("listening for events", component=COMPONENT, phase="P2", op="listen")
            while not conn.is_closed():
                await asyncio.sleep(5)
            log.warning("listener connection closed", component=COMPONENT, phase="P2", op="listen")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.warning(
                "listener error",
                component=COMPONENT,
                phase="P2",
                op="listen",
                error=type(exc).__name__,
            )
        finally:
            if conn is not None and not conn.is_closed():
                await conn.close()
        wait = BACKOFF_S[min(attempt, len(BACKOFF_S) - 1)] + random.random()
        attempt += 1
        await asyncio.sleep(wait)
