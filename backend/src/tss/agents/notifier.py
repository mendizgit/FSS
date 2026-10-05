"""F10 Notifier: push new BUY / SELL / bullT / bearT events to Telegram, exactly once each.

Delivery protocol: claim rows (notified_at set, committed) -> send -> on any failure release the
undelivered rows so the next run retries them. A crash between claim and send loses at most
that run's claimed alerts (never duplicates them).
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

from tss.agents.base import PARTIAL, SKIPPED, SUCCESS, AgentResult, BaseAgent, Deps
from tss.clients.telegram import TelegramClient, TelegramError, TelegramRateLimited
from tss.db.repositories import signals as signals_repo
from tss.domain.notifier import NOTIFY_EVENTS, format_event_message

MIN_INTERVAL_S = 1.1  # Telegram allows about one message per second per chat
MAX_PER_RUN = 20
MAX_RETRY_WAIT_S = 30.0

Sleep = Callable[[float], Awaitable[None]]


class NotifierAgent(BaseAgent):
    name = "notifier"
    critical = False

    def __init__(
        self,
        deps: Deps,
        telegram: TelegramClient | None,
        *,
        sleep: Sleep = asyncio.sleep,
        min_interval: float = MIN_INTERVAL_S,
        max_per_run: int = MAX_PER_RUN,
    ) -> None:
        super().__init__(deps)
        self._tg = telegram
        self._sleep = sleep
        self._min_interval = min_interval
        self._max_per_run = max_per_run

    async def _release(self, keys: list[signals_repo.EventKey]) -> None:
        if not keys:
            return
        async with self.deps.session_factory() as session:
            await signals_repo.release_events(session, keys)
            await session.commit()

    async def run(self, cycle_id: uuid.UUID, now: datetime) -> AgentResult:
        if self._tg is None:
            return AgentResult(status=SKIPPED, meta={"reason": "telegram_not_configured"})
        async with self.deps.session_factory() as session:
            claimed = await signals_repo.claim_events(
                session, now, NOTIFY_EVENTS, self._max_per_run
            )
            await session.commit()
        if not claimed:
            return AgentResult(status=SUCCESS, rows_in=0, rows_out=0, meta={"sent": 0})

        keys = [(s, tf, t, ev) for s, tf, t, ev, _ in claimed]
        pending = list(keys)
        sent: list[list[str]] = []
        error: TelegramError | None = None
        try:
            for index, (symbol, tf, _closed_at, event, against) in enumerate(claimed):
                text = format_event_message(
                    symbol=symbol, timeframe=tf, event=event, against_htf=against
                )
                if index > 0:
                    await self._sleep(self._min_interval)
                try:
                    await self._send(text)
                except TelegramError as exc:
                    error = exc
                    break
                pending.remove(keys[index])
                sent.append([symbol, tf, event])
        finally:
            # whatever was not delivered (failure, cancellation) goes back for the next run
            await asyncio.shield(self._release(pending))

        meta: dict[str, Any] = {
            "claimed": len(claimed),
            "sent": len(sent),
            "released": len(pending),
            "events": sent[:10],
        }
        if error is not None:
            meta["error"] = error.message
            if not sent:
                raise error  # nothing delivered: the run FAILED (rows were released above)
            return AgentResult(status=PARTIAL, rows_in=len(claimed), rows_out=len(sent), meta=meta)
        return AgentResult(status=SUCCESS, rows_in=len(claimed), rows_out=len(sent), meta=meta)

    async def _send(self, text: str) -> None:
        assert self._tg is not None
        try:
            await self._tg.send_message(text, html=True)
        except TelegramRateLimited as exc:
            if exc.retry_after > MAX_RETRY_WAIT_S:
                raise
            await self._sleep(exc.retry_after + 0.5)  # honour Telegram's flood control, once
            await self._tg.send_message(text, html=True)
