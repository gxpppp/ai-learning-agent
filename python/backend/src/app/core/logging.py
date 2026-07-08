"""Structured logging — JSON-formatted logs with trace context."""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any


class JsonFormatter(logging.Formatter):
    """JSON log formatter with trace_id and structured fields."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Attach trace context
        trace_id = getattr(record, "trace_id", None)
        if trace_id:
            log_entry["trace_id"] = trace_id

        agent = getattr(record, "agent", None)
        if agent:
            log_entry["agent"] = agent

        tool = getattr(record, "tool", None)
        if tool:
            log_entry["tool"] = tool

        duration_ms = getattr(record, "duration_ms", None)
        if duration_ms is not None:
            log_entry["duration_ms"] = duration_ms

        status = getattr(record, "status", None)
        if status:
            log_entry["status"] = status

        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = str(record.exc_info[1])

        return json.dumps(log_entry, ensure_ascii=False, default=str)


class TraceIdFilter(logging.Filter):
    """Injects trace_id into log records."""

    def __init__(self, trace_id: str | None = None):
        super().__init__()
        self.trace_id = trace_id or str(uuid.uuid4())[:8]

    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = self.trace_id  # type: ignore[attr-defined]
        return True


def setup_logging(level: int = logging.INFO) -> None:
    """Configure root logger with JSON output."""
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)


def get_logger(name: str, trace_id: str | None = None) -> logging.Logger:
    """Get a logger with optional trace context."""
    logger = logging.getLogger(name)
    if trace_id:
        logger.addFilter(TraceIdFilter(trace_id))
    return logger


def agent_log(name: str, **extra) -> logging.Logger:
    """Create a logger for an agent with extra fields."""
    logger = logging.getLogger(f"agent.{name}")
    return logger


def tool_log(name: str, duration_ms: int, status: str = "ok") -> str:
    """Format a tool execution log message."""
    return json.dumps({
        "tool": name,
        "duration_ms": duration_ms,
        "status": status,
    })
