"""Tests ensuring schema and prompt caching behaves as expected."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import yaml

from core import schema_registry
from llm import response_schemas
from prompts import PromptRegistry, clear_prompt_cache


def test_response_schema_cache_keyed_by_version(monkeypatch: Any) -> None:
    name = "cache_test_schema"
    calls = 0

    def _factory() -> dict[str, Any]:
        nonlocal calls
        calls += 1
        return {
            "type": "object",
            "properties": {"field": {"type": "string"}},
            "required": ["field"],
            "additionalProperties": False,
        }

    response_schemas.clear_response_schema_cache()
    response_schemas._SCHEMA_REGISTRY[name] = _factory  # type: ignore[attr-defined]

    try:
        first = response_schemas.get_response_schema(name, schema_version="v1")
        second = response_schemas.get_response_schema(name, schema_version="v1")
        assert first == second
        assert calls == 1

        response_schemas.get_response_schema(name, schema_version="v2")
        assert calls == 2
    finally:
        response_schemas._SCHEMA_REGISTRY.pop(name, None)  # type: ignore[attr-defined]
        response_schemas.clear_response_schema_cache()


def test_need_analysis_schema_cache_respects_version(monkeypatch: Any) -> None:
    calls = 0

    def _fake_builder(*, sections: Any = None) -> dict[str, Any]:  # noqa: ANN401
        nonlocal calls
        calls += 1
        return {"type": "object", "properties": {}, "required": []}

    monkeypatch.setattr("core.schema.build_need_analysis_responses_schema", _fake_builder)
    schema_registry.clear_schema_cache()

    first = schema_registry.load_need_analysis_schema(schema_version="1")
    second = schema_registry.load_need_analysis_schema(schema_version="1")
    assert first == second
    assert calls == 1

    schema_registry.load_need_analysis_schema(schema_version="2")
    assert calls == 2


def test_prompt_registry_caches_by_locale_and_version(tmp_path: Any, monkeypatch: Any) -> None:
    payload = {"section": {"greeting": {"en": "Hi", "de": "Hallo"}}}
    registry_path = tmp_path / "registry.yaml"
    registry_path.write_text(yaml.safe_dump(payload), encoding="utf-8")

    import prompts

    call_count = 0
    original_loader = prompts._load_registry_from_path

    @lru_cache(maxsize=4)
    def _counting_loader(path: Any, version: str | None) -> dict[str, Any]:
        nonlocal call_count
        call_count += 1
        return original_loader(path, version)

    monkeypatch.setattr(prompts, "_load_registry_from_path", _counting_loader)
    clear_prompt_cache()

    registry_v1 = PromptRegistry(path=registry_path, version="v1")
    assert registry_v1.get("section.greeting", locale="en") == "Hi"
    assert registry_v1.get("section.greeting", locale="en") == "Hi"
    assert call_count == 1

    assert registry_v1.get("section.greeting", locale="de") == "Hallo"
    assert call_count == 1

    registry_v2 = PromptRegistry(path=registry_path, version="v2")
    assert registry_v2.get("section.greeting", locale="en") == "Hi"
    assert call_count == 2

    clear_prompt_cache()
