"""Structured logging with contextvars + broadcaster integration."""

from __future__ import annotations

import json
import logging
import sys
import time
from contextvars import ContextVar
from typing import Any

current_task_id: ContextVar[int | None] = ContextVar("current_task_id", default=None)
current_worker_id: ContextVar[str | None] = ContextVar("current_worker_id", default=None)


class ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        record.task_id = current_task_id.get()
        record.worker_id = current_worker_id.get()
        return True


class JsonFormatter(logging.Formatter):
    _RESERVED = {
        "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
        "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
        "created", "msecs", "relativeCreated", "thread", "threadName",
        "processName", "process", "task_id", "worker_id", "message",
    }

    def format(self, record: logging.LogRecord) -> str:
        ts = time.gmtime(record.created)
        ts_str = time.strftime("%Y-%m-%dT%H:%M:%S", ts) + f".{int(record.msecs):03d}Z"
        out: dict[str, Any] = {
            "ts": ts_str,
            "level": record.levelname,
            "logger": record.name,
            "task_id": getattr(record, "task_id", None),
            "worker_id": getattr(record, "worker_id", None),
            "msg": record.getMessage(),
        }
        for k, v in record.__dict__.items():
            if k in self._RESERVED:
                continue
            try:
                json.dumps(v, default=str)
                out[k] = v
            except Exception:
                out[k] = repr(v)
        if record.exc_info:
            out["exc"] = self.formatException(record.exc_info)
        return json.dumps(out, ensure_ascii=False, default=str)


def record_to_dict(record: logging.LogRecord) -> dict[str, Any]:
    ts = time.gmtime(record.created)
    ts_str = time.strftime("%Y-%m-%dT%H:%M:%S", ts) + f".{int(record.msecs):03d}Z"
    extras: dict[str, Any] = {}
    for k, v in record.__dict__.items():
        if k in JsonFormatter._RESERVED:
            continue
        try:
            json.dumps(v, default=str)
            extras[k] = v
        except Exception:
            extras[k] = repr(v)
    return {
        "ts": ts_str,
        "level": record.levelname,
        "logger": record.name,
        "task_id": getattr(record, "task_id", None),
        "worker_id": getattr(record, "worker_id", None),
        "msg": record.getMessage(),
        **extras,
    }


def configure_logging(level: str, broadcaster: Any | None = None) -> None:
    from agent_clicker.observability.broadcaster import LogBroadcastHandler

    root = logging.getLogger()
    # remove existing handlers to avoid duplicates on reconfig
    for h in list(root.handlers):
        root.removeHandler(h)
    root.setLevel(level.upper())

    fmt = JsonFormatter()
    ctx = ContextFilter()

    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(fmt)
    stream.addFilter(ctx)
    root.addHandler(stream)

    if broadcaster is not None:
        bh = LogBroadcastHandler(broadcaster)
        bh.addFilter(ctx)
        root.addHandler(bh)

    # Tame noisy libs
    logging.getLogger("httpx").setLevel("WARNING")
    logging.getLogger("httpcore").setLevel("WARNING")
    logging.getLogger("uvicorn.access").setLevel("WARNING")
    logging.getLogger("sqlalchemy.engine").setLevel("WARNING")
