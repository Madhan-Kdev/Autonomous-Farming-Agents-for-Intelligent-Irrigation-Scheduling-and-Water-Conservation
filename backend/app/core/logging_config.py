"""
Structured logging configuration for the Autonomous Farming Agents backend.

Provides a factory function ``setup_logging`` that must be called once at
application startup.  All modules should obtain loggers via the standard
``logging.getLogger(__name__)`` mechanism after setup is complete.
"""

import logging
import sys
from typing import Any


class _TextFormatter(logging.Formatter):
    """Human-readable coloured formatter for development."""

    LEVEL_COLOURS = {
        logging.DEBUG: "\033[36m",     # Cyan
        logging.INFO: "\033[32m",      # Green
        logging.WARNING: "\033[33m",   # Yellow
        logging.ERROR: "\033[31m",     # Red
        logging.CRITICAL: "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:  # noqa: D102
        colour = self.LEVEL_COLOURS.get(record.levelno, "")
        level = f"{colour}{record.levelname:<8}{self.RESET}"
        name = f"\033[90m{record.name}\033[0m"
        message = super().format(record)
        # Replace the default levelname in the formatted string.
        message = message.replace(record.levelname, level, 1)
        return message


class _JsonFormatter(logging.Formatter):
    """Compact JSON formatter for production/structured logging."""

    def format(self, record: logging.LogRecord) -> str:  # noqa: D102
        import json
        import traceback

        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "line": record.lineno,
        }
        if record.exc_info:
            payload["exception"] = traceback.format_exception(*record.exc_info)
        return json.dumps(payload)


def setup_logging(level: str = "INFO", log_format: str = "text") -> None:
    """
    Configure the root logger for the application.

    Parameters
    ----------
    level:
        Log level string (DEBUG, INFO, WARNING, ERROR, CRITICAL).
    log_format:
        ``"text"`` for human-readable output (development) or
        ``"json"`` for structured output (production).

    Call this function **once** at application startup before any other
    module uses ``logging.getLogger``.
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    if log_format == "json":
        handler.setFormatter(_JsonFormatter())
    else:
        formatter = _TextFormatter(
            fmt="%(levelname)s %(asctime)s %(name)s — %(message)s",
            datefmt="%H:%M:%S",
        )
        handler.setFormatter(formatter)

    # Suppress noisy third-party loggers.
    for noisy in ("uvicorn.access", "httpx", "httpcore", "sqlalchemy.engine"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(numeric_level)

    logging.getLogger(__name__).debug(
        "Logging configured: level=%s format=%s", level, log_format
    )


def get_logger(name: str) -> logging.Logger:
    """
    Convenience wrapper around ``logging.getLogger``.

    Usage::

        from app.core.logging_config import get_logger
        logger = get_logger(__name__)
    """
    return logging.getLogger(name)
