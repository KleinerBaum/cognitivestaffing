"""Strict nano-only routing tests for config and router helpers."""

from __future__ import annotations

import importlib

import config
import config.models as model_config


def test_configure_models_enforces_nano_for_all_generation_tasks() -> None:
    model_config.configure_models(
        reasoning_effort="low",
        lightweight_override=model_config.GPT4O_MINI,
        medium_reasoning_override=model_config.O3,
        high_reasoning_override=model_config.GPT52,
        primary_override=model_config.GPT4,
        default_override=model_config.GPT4O,
        openai_override=model_config.O4_MINI,
        model_routing_overrides={
            model_config.ModelTask.JOB_AD.value: model_config.GPT4O,
            model_config.ModelTask.EXPLANATION.value: model_config.O3,
            "embedding": model_config.EMBED_MODEL,
        },
        strict_nano_only=True,
    )

    assert model_config.LIGHTWEIGHT_MODEL == model_config.GPT51_NANO
    assert model_config.MEDIUM_REASONING_MODEL == model_config.GPT51_NANO
    assert model_config.HIGH_REASONING_MODEL == model_config.GPT51_NANO
    assert model_config.REASONING_MODEL == model_config.GPT51_NANO
    assert model_config.DEFAULT_MODEL == model_config.GPT51_NANO
    assert model_config.OPENAI_MODEL == model_config.GPT51_NANO

    for task, routed_model in model_config.MODEL_ROUTING.items():
        if task == "embedding":
            assert routed_model == model_config.EMBED_MODEL
            continue
        assert routed_model == model_config.GPT51_NANO


def test_strict_mode_fallback_chains_remain_single_family() -> None:
    model_config.configure_models(reasoning_effort="minimal", strict_nano_only=True)

    for task, fallback_chain in model_config.TASK_MODEL_FALLBACKS.items():
        if task == "embedding":
            assert fallback_chain == [model_config.EMBED_MODEL]
            continue
        assert fallback_chain == [model_config.GPT51_NANO]


def test_quick_and_precise_both_route_to_nano() -> None:
    model_config.configure_models(reasoning_effort="minimal", strict_nano_only=True)
    quick = model_config.get_model_for(model_config.ModelTask.JOB_AD)

    model_config.configure_models(reasoning_effort="high", strict_nano_only=True)
    precise = model_config.get_model_for(model_config.ModelTask.JOB_AD)

    assert quick == model_config.GPT51_NANO
    assert precise == model_config.GPT51_NANO


def test_env_overrides_cannot_escape_strict_nano(monkeypatch) -> None:
    monkeypatch.setenv("STRICT_NANO_ONLY", "1")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("DEFAULT_MODEL", "o3")
    monkeypatch.setenv("LIGHTWEIGHT_MODEL", "gpt-4.1-nano")
    monkeypatch.setenv("MEDIUM_REASONING_MODEL", "gpt-4o")
    monkeypatch.setenv("HIGH_REASONING_MODEL", "o4-mini")
    monkeypatch.setenv("MODEL_ROUTING__job_ad", "gpt-4")

    reloaded_config = importlib.reload(config)

    assert reloaded_config.STRICT_NANO_ONLY is True
    assert reloaded_config.OPENAI_MODEL == model_config.GPT51_NANO
    assert reloaded_config.DEFAULT_MODEL == model_config.GPT51_NANO
    assert reloaded_config.LIGHTWEIGHT_MODEL == model_config.GPT51_NANO
    assert reloaded_config.MEDIUM_REASONING_MODEL == model_config.GPT51_NANO
    assert reloaded_config.HIGH_REASONING_MODEL == model_config.GPT51_NANO
    assert reloaded_config.MODEL_ROUTING[model_config.ModelTask.JOB_AD.value] == model_config.GPT51_NANO

    importlib.reload(config)
