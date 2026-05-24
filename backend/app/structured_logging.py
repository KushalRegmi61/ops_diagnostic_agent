"""Structured logging setup and context helpers."""
import logging
import sys
import time
from typing import Any

import structlog

from app.config import get_settings


def _normalize_event_name(_logger: Any, _method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """Render internal dotted event names like the snake-case service logs we use elsewhere."""
    event = event_dict.get("event")
    if isinstance(event, str):
        event_dict["event"] = event.replace(".", "_")
    return event_dict


def _add_level_icon(_logger: Any, _method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """Prefix console events with a small visual marker for fast log scanning."""
    event = event_dict.get("event")
    if not isinstance(event, str):
        return event_dict

    level = str(event_dict.get("level", _method_name)).lower()
    icon = {
        "debug": "🔎",
        "info": "✅",
        "warning": "⚠️",
        "error": "❌",
        "critical": "🚨",
    }.get(level, "•")
    event_dict["event"] = f"{icon} {event}"
    return event_dict


def configure_logging() -> None:
    """Configure stdlib logging + structlog once per process."""
    settings = get_settings()
    log_level = settings.log_level.upper()
    is_json = settings.log_format == "json"
    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        timestamper,
        _normalize_event_name,
        structlog.processors.StackInfoRenderer(),
    ]
    if not is_json:
        shared_processors.insert(-1, _add_level_icon)

    renderer = (
        structlog.processors.JSONRenderer()
        if is_json
        else structlog.dev.ConsoleRenderer(colors=True, sort_keys=False)
    )
    formatter = structlog.stdlib.ProcessorFormatter(
        fmt=(
            "%(message)s"
            if is_json
            else "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        ),
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.format_exc_info,
            renderer,
        ],
        foreign_pre_chain=shared_processors,
    )
    formatter.converter = time.gmtime
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, log_level, logging.INFO))

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.processors.format_exc_info,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a module-scoped structured logger."""
    return structlog.get_logger(name)


def bind_context(**values: Any) -> None:
    """Attach fields to every subsequent log record in the current context."""
    structlog.contextvars.bind_contextvars(**{k: v for k, v in values.items() if v is not None})


def clear_context() -> None:
    """Clear request/run-local log contextvars."""
    structlog.contextvars.clear_contextvars()
