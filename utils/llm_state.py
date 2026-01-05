"""Helpers for gating LLM-powered features based on session state."""

from __future__ import annotations

from typing import Any
from types import ModuleType

_streamlit_mod: ModuleType | None
try:  # pragma: no cover - streamlit is optional during certain tests
    from typing_shims import streamlit as _streamlit_mod
except Exception:  # pragma: no cover - fallback when Streamlit is unavailable
    _streamlit_mod = None

st: ModuleType | None = _streamlit_mod

from config import is_llm_enabled
from utils.i18n import tr

__all__ = [
    "is_llm_available",
    "llm_disabled_message",
    "raise_if_llm_unavailable",
]


def _session_state() -> Any:
    """Return the Streamlit session state if accessible."""

    if st is None:  # pragma: no cover - no Streamlit context available
        return None
    try:
        return st.session_state
    except Exception:  # pragma: no cover - Streamlit not initialised
        return None


def is_llm_available() -> bool:
    """Return ``True`` if LLM-powered features may be used."""

    session = _session_state()
    if session is not None:
        if session.get("openai_unavailable"):
            return False
        if "openai_api_key_missing" in session:
            return not bool(session.get("openai_api_key_missing"))
    return is_llm_enabled()


def llm_disabled_message(*, lang: str | None = None) -> str:
    """Return a bilingual message explaining that the API key is missing."""

    return tr(
        "🔒 KI-Funktionen deaktiviert. Hinterlege einen OpenAI API Key in den Einstellungen.",
        "🔒 AI features are disabled. Add an OpenAI API key in the settings.",
        lang=lang,
    )


def raise_if_llm_unavailable(action: str | None = None) -> None:
    """Raise ``RuntimeError`` when LLM features are disabled."""

    if is_llm_available():
        return
    hint = llm_disabled_message()
    if action:
        raise RuntimeError(f"{hint} ({action}).")
    raise RuntimeError(hint)
