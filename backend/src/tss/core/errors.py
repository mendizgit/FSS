"""TSS error types. Every error carries component, phase and operation."""

from __future__ import annotations

from typing import Any


class TSSError(Exception):
    """Base error: names the component, phase and operation that failed."""

    def __init__(
        self,
        component: str,
        phase: str,
        operation: str,
        message: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        self.component = component
        self.phase = phase
        self.operation = operation
        self.message = message
        self.context: dict[str, Any] = context or {}
        super().__init__(self.__str__())

    def __str__(self) -> str:
        return (
            f"[TSS] component={self.component} phase={self.phase} "
            f"op={self.operation}\n      error={self.message}"
        )


class DataSourceError(TSSError):
    """An external data source failed or returned an unexpected shape."""


class ValidationError(TSSError):
    """Input or payload validation failed."""


class CalculationError(TSSError):
    """A domain calculation could not be completed."""


class ConfigError(TSSError):
    """Configuration (env or YAML) is missing or invalid."""


class StorageError(TSSError):
    """Database read/write failed."""
