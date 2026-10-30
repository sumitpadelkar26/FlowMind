"""Structured JSON logging with a per-request correlation ID.

- One JSON object per line, written to a rotating file AND the console.
- request_id lives in a ContextVar so every log line inside a request carries it.
- Secrets (API keys) are redacted before they reach any handler.
"""
import json
import logging
import os
import re
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler

from .config import settings

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

_SECRET_PATTERNS = [
    re.compile(r"(key=)[^&\s\"']+", re.I),
    re.compile(r"(api[_-]?key\"?\s*[:=]\s*\"?)[^\s\",}]+", re.I),
    re.compile(r"(bearer\s+)[A-Za-z0-9._\-]+", re.I),
    re.compile(r"AIza[0-9A-Za-z_\-]{20,}"),
]
_RESERVED = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys()) | {"message", "asctime"}


def redact(text: str) -> str:
    for pat in _SECRET_PATTERNS:
        text = pat.sub(lambda m: (m.group(1) + "***") if m.groups() else "***", text)
    if settings.ai_api_key:
        text = text.replace(settings.ai_api_key, "***")
    return text


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "request_id": request_id_var.get(),
            "event": record.getMessage(),
        }
        for k, v in record.__dict__.items():
            if k not in _RESERVED and not k.startswith("_"):
                payload[k] = v
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return redact(json.dumps(payload, default=str))


def setup_logging() -> None:
    root = logging.getLogger()
    if getattr(root, "_configured", False):
        return
    fmt = JsonFormatter()
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    # Vercel's function bundle is read-only. Its platform captures stdout/stderr,
    # so use console logging there and retain rotating local files for development.
    if os.getenv("VERCEL"):
        root.handlers = [console]
    else:
        os.makedirs(os.path.dirname(settings.log_file) or ".", exist_ok=True)
        file_h = RotatingFileHandler(settings.log_file, maxBytes=2_000_000, backupCount=5, encoding="utf-8")
        file_h.setFormatter(fmt)
        root.handlers = [file_h, console]
    root.setLevel(settings.log_level)
    for noisy in ("httpx", "httpcore", "uvicorn.access"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    root._configured = True  # type: ignore[attr-defined]


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def new_request_id() -> str:
    return uuid.uuid4().hex[:12]
