from pathlib import Path
import sys
import types
from dataclasses import dataclass

import streamlit as st

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config


@pytest.fixture(autouse=True)
def _stub_agents_module() -> None:
    """Ensure the lightweight agents shim is always available during tests."""

    if "agents" not in sys.modules:
        shim = types.ModuleType("agents")

        def _function_tool(func):  # type: ignore[return-type]
            return func

        shim.function_tool = _function_tool  # type: ignore[attr-defined]
        sys.modules["agents"] = shim
    yield


@pytest.fixture(autouse=True)
def _ensure_test_openai_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provide a deterministic OpenAI API key during tests unless overridden."""

    monkeypatch.setattr(config, "OPENAI_API_KEY", "test-key", raising=False)
    monkeypatch.setattr(config, "LLM_ENABLED", True, raising=False)
    try:
        import openai_utils.api as openai_api

        monkeypatch.setattr(openai_api, "OPENAI_API_KEY", "test-key", raising=False)
    except Exception:
        pass
    yield


@dataclass
class _SessionDict(dict[str, object]):
    """Lightweight replacement for ``st.session_state`` during tests."""

    def clear(self) -> None:  # type: ignore[override]
        super().clear()


@pytest.fixture(autouse=True)
def _stub_streamlit_session_state(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace Streamlit's runtime-bound session state with a plain dictionary."""

    session_state = _SessionDict()
    monkeypatch.setattr(st, "session_state", session_state, raising=False)
    yield
