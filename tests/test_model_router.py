"""Tests for the dynamic OpenAI model router."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterable, Sequence

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import llm.model_router as model_router


class FakeModel:
    """Simple value object mirroring the OpenAI model payload."""

    def __init__(self, model_id: str) -> None:
        self.id = model_id


class FakeModelResource:
    """Emulates the ``client.models`` accessor of the OpenAI SDK."""

    def __init__(self, model_ids: Sequence[str]) -> None:
        self._model_ids = list(model_ids)
        self.list_calls = 0

    def list(self) -> Iterable[FakeModel]:
        self.list_calls += 1
        for model_id in self._model_ids:
            yield FakeModel(model_id)


class FakeOpenAIClient:
    """Mimics the subset of the OpenAI client used by the router."""

    def __init__(self, model_ids: Sequence[str]) -> None:
        self.models = FakeModelResource(model_ids)


@pytest.fixture(autouse=True)
def clear_router_state(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reset router caches and environment variables between tests."""

    monkeypatch.delenv(model_router.PREF_ENV, raising=False)
    monkeypatch.delenv(model_router.FB_ENV, raising=False)
    model_router._available_models.cache_clear()  # type: ignore[attr-defined]


def test_prefers_explicit_environment_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """A preferred model configured via env vars should win when available."""

    monkeypatch.setenv(model_router.PREF_ENV, "o4-mini")
    client = FakeOpenAIClient(["gpt-4o", "o4-mini"])

    chosen = model_router.pick_model(client)

    assert chosen == "o4-mini"


def test_env_fallback_chain_respected(monkeypatch: pytest.MonkeyPatch) -> None:
    """Configured fallback models are evaluated in-order when preferred fails."""

    monkeypatch.setenv(model_router.FB_ENV, "does-not-exist,gpt-4o")
    client = FakeOpenAIClient(["gpt-4o"])

    chosen = model_router.pick_model(client)

    assert chosen == "gpt-4o"


def test_aliases_map_to_supported_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """Legacy IDs should be normalised using the alias mapping."""

    monkeypatch.setenv(model_router.PREF_ENV, "gpt-5.1-mini")
    client = FakeOpenAIClient(["gpt-4.1-mini"])

    chosen = model_router.pick_model(client)

    assert chosen == "gpt-4.1-mini"


def test_default_candidates_used_when_no_env_overrides() -> None:
    """The router falls back to the built-in candidate list."""

    client = FakeOpenAIClient(["gpt-4o"])

    chosen = model_router.pick_model(client)

    assert chosen == "gpt-4o"


def test_raises_when_no_candidates_available() -> None:
    """A descriptive runtime error is raised when nothing matches."""

    client = FakeOpenAIClient(["some-other-model"])

    with pytest.raises(RuntimeError) as excinfo:
        model_router.pick_model(client)

    message = str(excinfo.value)
    assert "No usable model found" in message
    assert "some-other-model" in message


def test_available_models_cached_for_same_client() -> None:
    """Subsequent calls reuse cached availability results for a client."""

    client = FakeOpenAIClient(["gpt-4o"])

    first = model_router.pick_model(client)
    second = model_router.pick_model(client)

    assert first == second == "gpt-4o"
    assert client.models.list_calls == 1
