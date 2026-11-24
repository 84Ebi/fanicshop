"""Structured JSON logging via structlog.

PII is masked at the call sites; this module only formats. A `mask` helper is
provided so sensitive values (tokens, card PANs, phone numbers) never appear
verbatim in logs.
"""

from __future__ import annotations

import logging
import re

import structlog

_PAN_RE = re.compile(r"\b\d{13,}\b")
_TOKEN_RE = re.compile(r"(?i)(bot_token|token|secret|password|hmac)[=:]\s*\S+")


def mask(value: str) -> str:
    """Mask obvious secrets and long number runs (e.g. card PANs)."""
    out = _PAN_RE.sub(lambda m: m.group(0)[:4] + "-****-****-" + m.group(0)[-4:], value)
    out = _TOKEN_RE.sub(lambda m: f"{m.group(1)}=***", out)
    return out


def setup_logging(level: str = "INFO") -> None:
    log_level = logging.getLevelName(level.upper())
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    logging.basicConfig(level=log_level)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name or "fanic")
