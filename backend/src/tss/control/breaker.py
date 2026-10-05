"""Per-agent circuit breaker (Arch §8): opens after N consecutive failed runs, then cools down."""

from __future__ import annotations

from datetime import datetime, timedelta


class CircuitBreaker:
    def __init__(self, failures: int, cooldown_s: int) -> None:
        self._threshold = failures
        self._cooldown = timedelta(seconds=cooldown_s)
        self.consecutive_failures = 0
        self.opened_at: datetime | None = None

    def is_open(self, now: datetime) -> bool:
        return self.opened_at is not None and now - self.opened_at < self._cooldown

    def allow(self, now: datetime) -> bool:
        """Closed, or the cooldown elapsed (half-open: one trial run is allowed)."""
        return not self.is_open(now)

    def record_success(self) -> None:
        self.consecutive_failures = 0
        self.opened_at = None

    def record_failure(self, now: datetime) -> None:
        self.consecutive_failures += 1
        if self.consecutive_failures >= self._threshold:
            self.opened_at = now  # (re)open; a failed half-open trial restarts the cooldown

    def reset(self) -> None:
        self.record_success()
