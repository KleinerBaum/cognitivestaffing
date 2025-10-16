"""Configuration loader for OpenAI access and debug flags.

Reads environment variables or Streamlit secrets and exposes
settings used across the project. A clear runtime error is raised
if the OpenAI API key is missing.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

try:  # pragma: no cover - streamlit not always available
    import streamlit as st
except Exception:  # pragma: no cover
    st = None  # type: ignore


@dataclass(slots=True)
class Settings:
    """Runtime configuration values.

    Attributes:
        openai_api_key: Secret key for the OpenAI API.
        openai_org: Optional OpenAI organization identifier.
        json_mode: Whether to request JSON responses from the model.
        function_calling: Whether to enable function-calling mode.
        debug_logs: Toggle verbose debug logging.
    """

    openai_api_key: str
    openai_org: Optional[str]
    json_mode: bool
    function_calling: bool
    debug_logs: bool


def _as_bool(value: Optional[str]) -> bool:
    """Interpret truthy string values as boolean True."""

    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_settings() -> Settings:
    """Load settings from env vars or Streamlit secrets.

    Raises:
        RuntimeError: If ``OPENAI_API_KEY`` is missing.
    """

    secrets: dict[str, str] = {}
    if st is not None:
        try:
            secrets = dict(st.secrets)
        except Exception:  # pragma: no cover - defensive
            secrets = {}

    def _get(key: str) -> Optional[str]:
        return secrets.get(key) or os.getenv(key)

    api_key = _get("OPENAI_API_KEY")
    org = _get("OPENAI_ORG")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is missing. Set the variable or define it in st.secrets.")

    return Settings(
        openai_api_key=api_key,
        openai_org=org,
        json_mode=_as_bool(_get("JSON_MODE")),
        function_calling=_as_bool(_get("FUNCTION_CALLING")),
        debug_logs=_as_bool(_get("DEBUG_LOGS")),
    )


__all__ = ["Settings", "load_settings"]
