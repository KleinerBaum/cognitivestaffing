from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config


@pytest.fixture(autouse=True)
def _ensure_test_openai_key(monkeypatch):
    """Provide a deterministic OpenAI API key during tests unless overridden."""

    monkeypatch.setattr(config, "OPENAI_API_KEY", "test-key", raising=False)
    monkeypatch.setattr(config, "LLM_ENABLED", True, raising=False)
    try:
        import openai_utils.api as openai_api

        monkeypatch.setattr(openai_api, "OPENAI_API_KEY", "test-key", raising=False)
    except Exception:
        pass
    yield
