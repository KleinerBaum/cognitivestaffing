"""Structured logging utilities for Vacalyser."""

from __future__ import annotations

import json
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Dict

LOGGER = logging.getLogger("vacalyser")


def _redact(value: str) -> str:
    """Redact known secrets from a string."""

    secrets = [os.getenv("OPENAI_API_KEY"), os.getenv("SECRET_KEY")]
    for secret in secrets:
        if secret:
            value = value.replace(secret, "[redacted]")
    return value


def log_event(
    level: str,
    *,
    task_id: str | None = None,
    model: str | None = None,
    tokens: int | None = None,
    duration: float | None = None,
    payload: Dict[str, Any] | None = None,
) -> str:
    """Emit a structured log line and optionally dump payload to a temp file.

    Args:
        level: Logging level name (e.g., ``"info"``).
        task_id: Optional task identifier.
        model: Model name used for the call.
        tokens: Token count for the request.
        duration: Duration of the operation in seconds.
        payload: Optional payload to dump for debugging when
            ``VACAYSER_DEBUG`` env var is truthy.

    Returns:
        Path to the dumped payload file if written, else an empty string.
    """

    record = {
        "level": level.lower(),
        "task_id": task_id,
        "model": model,
        "tokens": tokens,
        "duration": duration,
    }
    safe_record = {k: _redact(str(v)) for k, v in record.items() if v is not None}
    LOGGER.log(getattr(logging, level.upper(), logging.INFO), json.dumps(safe_record))

    if payload and os.getenv("VACAYSER_DEBUG"):
        path = Path(tempfile.gettempdir()) / f"vacalyser_{int(time.time())}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
        return str(path)
    return ""
