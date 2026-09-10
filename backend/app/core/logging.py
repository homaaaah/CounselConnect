"""Sensitive-data-safe logging configuration.

Rules (docs/SECURITY.md): confidential values (COR references, message
bodies, SOS answers, tokens, student identifiers) must never reach routine
logs. Helpers here redact known-sensitive keys; always prefer structured
safe_kwargs over raw interpolation.
"""

from __future__ import annotations

import logging
import re

_SENSITIVE_KEYS = re.compile(
    r"(password|token|secret|cor_|storage_key|body|answer|conversation)",
    re.IGNORECASE,
)

REDACTED = "[REDACTED]"


def safe_kwargs(kwargs: dict[str, object]) -> dict[str, object]:
    """Return a copy of kwargs with sensitive keys replaced by [REDACTED]."""
    return {k: (REDACTED if _SENSITIVE_KEYS.search(k) else v) for k, v in kwargs.items()}


def configure_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(level=level, format="%(levelname)s %(name)s %(message)s")
