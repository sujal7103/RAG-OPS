"""Structured logging and request-context helpers."""

from __future__ import annotations

import contextvars
import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

from rag_ops.settings import ServiceSettings

_request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


def set_request_id(request_id: str) -> contextvars.Token[str]:
    """Bind a request identifier to the current context."""
    return _request_id_var.set(request_id)


def reset_request_id(token: contextvars.Token[str]) -> None:
    """Reset the bound request identifier."""
    _request_id_var.reset(token)


def get_request_id() -> str:
    """Return the current request identifier if set."""
    return _request_id_var.get()


class RequestContextFilter(logging.Filter):
    """Inject request-context values into log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True


class JsonFormatter(logging.Formatter):
    """Format log records as compact JSON payloads."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "stage"):
            payload["stage"] = record.stage
        return json.dumps(payload, ensure_ascii=True, sort_keys=True)


def configure_logging(settings: ServiceSettings) -> None:
    """Configure root logging for the current process."""
    root_logger = logging.getLogger()
    if getattr(root_logger, "_rag_ops_configured", False):
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RequestContextFilter())
    if settings.json_logs:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)s | %(name)s | request_id=%(request_id)s | %(message)s"
            )
        )

    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
    root_logger._rag_ops_configured = True  # type: ignore[attr-defined]
