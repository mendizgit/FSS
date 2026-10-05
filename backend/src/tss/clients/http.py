"""Shared HTTP layer: timeouts, retry with backoff, per-host rate limiter, Retry-After.

All external HTTP goes through `HttpClient` (EXECUTION_RULES §8). Error context carries the
endpoint path only, never the full URL or query string.
"""

from __future__ import annotations

import asyncio
import random
import time
from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import urlsplit

import httpx

from tss.core.errors import DataSourceError
from tss.core.logging import get_logger

PHASE = "P1"
BACKOFF_S = (2.0, 4.0, 8.0)  # Arch §8: 3 retries after the first attempt
RETRY_STATUS = frozenset({429, 500, 502, 503, 504})
TIMEOUT = httpx.Timeout(15.0, connect=5.0)
MAX_RETRY_AFTER_S = 30.0

Sleep = Callable[[float], Awaitable[None]]


class RateLimiter:
    """Spaces requests to one host by at least 1 / rps seconds."""

    def __init__(self, rps: float, clock: Callable[[], float] = time.monotonic) -> None:
        self._interval = 1.0 / rps
        self._clock = clock
        self._next = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self, sleep: Sleep = asyncio.sleep) -> None:
        async with self._lock:
            now = self._clock()
            wait = self._next - now
            self._next = max(now, self._next) + self._interval
        if wait > 0:
            await sleep(wait)


def _retry_after(resp: httpx.Response) -> float | None:
    raw = resp.headers.get("Retry-After")
    if raw is None:
        return None
    try:
        return min(max(float(raw), 0.0), MAX_RETRY_AFTER_S)
    except ValueError:
        return None


class HttpClient:
    def __init__(
        self,
        rps_by_host: dict[str, float],
        *,
        client: httpx.AsyncClient | None = None,
        sleep: Sleep = asyncio.sleep,
        jitter: Callable[[], float] = random.random,
    ) -> None:
        self._client = client or httpx.AsyncClient(
            timeout=TIMEOUT, headers={"User-Agent": "tss/0.1 (market analysis)"}
        )
        self._limiters = {host: RateLimiter(rps) for host, rps in rps_by_host.items()}
        self._sleep = sleep
        self._jitter = jitter
        self._log = get_logger("http")

    async def aclose(self) -> None:
        await self._client.aclose()

    async def get_json(
        self,
        url: str,
        *,
        component: str,
        operation: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        parts = urlsplit(url)
        path = parts.path
        limiter = self._limiters.get(parts.netloc)
        last: str = "unknown error"
        status: int | None = None
        for attempt in range(len(BACKOFF_S) + 1):
            if limiter is not None:
                await limiter.acquire(self._sleep)
            delay: float | None = None
            try:
                resp = await self._client.get(url, params=params)
                status = resp.status_code
                if status in RETRY_STATUS:
                    last = f"HTTP {status}"
                    delay = _retry_after(resp)
                else:
                    resp.raise_for_status()
                    return resp.json()
            except httpx.HTTPStatusError as exc:
                raise DataSourceError(
                    component,
                    PHASE,
                    operation,
                    f"HTTP {exc.response.status_code} from {path}",
                    {"endpoint": path, "status": exc.response.status_code},
                ) from exc
            except ValueError as exc:  # invalid JSON body
                raise DataSourceError(
                    component,
                    PHASE,
                    operation,
                    f"response from {path} is not valid JSON",
                    {"endpoint": path},
                ) from exc
            except httpx.TransportError as exc:
                last = type(exc).__name__
            if attempt < len(BACKOFF_S):
                wait = delay if delay is not None else BACKOFF_S[attempt] + self._jitter()
                self._log.warning(
                    "retrying",
                    component=component,
                    phase=PHASE,
                    op=operation,
                    endpoint=path,
                    attempt=attempt + 1,
                    reason=last,
                    wait_s=round(wait, 2),
                )
                await self._sleep(wait)
        raise DataSourceError(
            component,
            PHASE,
            operation,
            f"{path} failed after {len(BACKOFF_S) + 1} attempts ({last})",
            {"endpoint": path, "status": status},
        )
