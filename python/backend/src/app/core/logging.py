"""Structured logging — JSON lines with trace_id, timestamp, and context fields.

Usage:
    from app.core.logging import get_logger
    logger = get_logger(__name__)
    logger.info("message", extra={"trace_id": tid, "tool": "create_folder"})
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
import uuid
from logging.handlers import RotatingFileHandler
from pathlib import Path


ROOT_LOGGER = "ai-tutor"


class _CompactFormatter(logging.Formatter):
    """JSON-lines formatter. Reads `extra` dict from LogRecord."""

    def format(self, record: logging.LogRecord) -> str:
        ts = time.strftime("%H:%M:%S", time.localtime(record.created))
        entry = {
            "ts": ts,
            "lvl": record.levelname,
            "src": record.name.replace("app.", ""),
            "msg": record.getMessage(),
        }
        for key in ("trace_id", "tool", "args", "result", "ms", "vault", "error"):
            val = getattr(record, key, None)
            if val is not None:
                entry[key] = str(val)[:200]
        if record.exc_info and record.exc_info[1]:
            entry["exc"] = str(record.exc_info[1])[:300]
        return json.dumps(entry, ensure_ascii=False, default=str)


class _TraceFilter(logging.Filter):
    """Injects trace_id into every record."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not getattr(record, "trace_id", None):
            record.trace_id = "------"
        return True


def setup_logging(log_dir: str = "") -> None:
    """Configure root logger with JSON stdout + rotating file."""
    fmt = _CompactFormatter()
    trace_filter = _TraceFilter()

    # Stdout (Obsidian dev console)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    sh.addFilter(trace_filter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(sh)
    root.setLevel(logging.INFO)

    # File log (if vault path available)
    if log_dir:
        try:
            os.makedirs(log_dir, exist_ok=True)
            fh = RotatingFileHandler(
                os.path.join(log_dir, "backend.log"),
                maxBytes=5 * 1024 * 1024,
                backupCount=2,
                encoding="utf-8",
            )
            fh.setFormatter(fmt)
            fh.addFilter(trace_filter)
            root.addHandler(fh)
            logging.getLogger(ROOT_LOGGER).info("log file ready",
                extra={"path": os.path.join(log_dir, "backend.log")})
        except Exception:
            pass


def get_logger(name: str) -> logging.Logger:
    """Get a logger — automatically strips 'app.' prefix for compact output."""
    return logging.getLogger(name)


def new_trace_id() -> str:
    return uuid.uuid4().hex[:8]


def tool_extra(trace_id: str, tool: str, **kw: str) -> dict:
    return {"trace_id": trace_id, "tool": tool, **kw}
