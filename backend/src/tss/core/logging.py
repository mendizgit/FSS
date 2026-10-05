"""structlog JSON logging with secret redaction and bound component/phase/op/cycle_id."""

from __future__ import annotations

import logging
import re
import sys
from collections.abc import MutableMapping
from typing import Any

import structlog
from pydantic import SecretBytes, SecretStr

REDACTED = "***REDACTED***"
_SENSITIVE_KEY = re.compile(
    r"(token|secret|password|passwd|api[_-]?key|hash|authorization|cookie|database_url|dsn)",
    re.IGNORECASE,
)
# user:password@ inside URLs
_URL_CREDENTIALS = re.compile(r"(://[^/\s:@]+:)[^@\s/]+(@)")

_CONTEXT_KEYS = ("component", "phase", "op", "cycle_id")


def _redact_value(value: Any) -> Any:
    if isinstance(value, SecretStr | SecretBytes):
        return REDACTED
    if isinstance(value, str):
        return _URL_CREDENTIALS.sub(rf"\1{REDACTED}\2", value)
    if isinstance(value, dict):
        return _redact_mapping(value)
    if isinstance(value, list | tuple):
        return [_redact_value(v) for v in value]
    return value


def _redact_mapping(data: MutableMapping[Any, Any]) -> dict[Any, Any]:
    out: dict[Any, Any] = {}
    for key, value in data.items():
        if isinstance(key, str) and _SENSITIVE_KEY.search(key):
            out[key] = REDACTED
        else:
            out[key] = _redact_value(value)
    return out


def redact_processor(
    _logger: Any, _method: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    return _redact_mapping(event_dict)


def ensure_context_processor(
    _logger: Any, _method: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    for key in _CONTEXT_KEYS:
        event_dict.setdefault(key, None)
    return event_dict


def configure_logging(level: str = "INFO") -> None:
    level_no = logging.getLevelNamesMapping().get(level.upper(), logging.INFO)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            ensure_context_processor,
            structlog.processors.format_exc_info,
            redact_processor,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level_no),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.typing.FilteringBoundLogger:
    logger: structlog.typing.FilteringBoundLogger = structlog.get_logger(name)
    return logger


def bind_context(
    *,
    component: str | None = None,
    phase: str | None = None,
    op: str | None = None,
    cycle_id: str | None = None,
) -> None:
    """Bind run context for subsequent log lines in this task/thread."""
    values = {"component": component, "phase": phase, "op": op, "cycle_id": cycle_id}
    structlog.contextvars.bind_contextvars(**{k: v for k, v in values.items() if v is not None})


def clear_context() -> None:
    structlog.contextvars.clear_contextvars()
