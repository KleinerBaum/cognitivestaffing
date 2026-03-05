"""Ensure model configuration is centralised and capability-aware."""

from __future__ import annotations

import pytest

import config
from config import ModelTask, get_task_config
from config.models import TaskModelConfig


def test_all_model_tasks_have_config_entry() -> None:
    """Every ``ModelTask`` should map to a declared configuration entry."""

    for task in ModelTask:
        config_entry = get_task_config(task)
        assert isinstance(config_entry, TaskModelConfig)
        assert config_entry.model
        assert task.value in config.MODEL_CONFIG


@pytest.mark.parametrize(
    "task",
    [ModelTask.TEAM_ADVICE],
)
def test_text_only_tasks_disable_json(task: ModelTask) -> None:
    """Certain conversational tasks must avoid JSON and response-formatting."""

    config_entry = get_task_config(task)
    assert config_entry.allow_json_schema is False
    assert config_entry.allow_response_format is False


@pytest.mark.parametrize(
    "task",
    [ModelTask.EXTRACTION, ModelTask.JSON_REPAIR, ModelTask.FOLLOW_UP_QUESTIONS],
)
def test_json_tasks_allow_schema(task: ModelTask) -> None:
    """Structured tasks should keep JSON schema and response formatting enabled."""

    config_entry = get_task_config(task)
    assert config_entry.allow_json_schema is True
    assert config_entry.allow_response_format is True


def test_gpt35_disables_schema_capabilities() -> None:
    """Legacy gpt-3.5 models should not advertise structured output support."""

    capabilities = config.get_model_capabilities("gpt-3.5-turbo")
    assert capabilities.supports_json_schema is False
    assert capabilities.supports_response_format is False


def test_task_fallbacks_prioritise_schema_capable_models() -> None:
    """Structured chain should keep schema-capable models before text-only fallback."""

    fallbacks = config.get_task_fallbacks(ModelTask.EXTRACTION)
    assert fallbacks

    first_non_schema_index: int | None = None
    for index, model_name in enumerate(fallbacks):
        capabilities = config.get_model_capabilities(model_name)
        if not capabilities.supports_json_schema:
            first_non_schema_index = index
            break

    if first_non_schema_index is None:
        return

    for model_name in fallbacks[:first_non_schema_index]:
        capabilities = config.get_model_capabilities(model_name)
        assert capabilities.supports_json_schema is True


def test_task_fallbacks_match_model_candidates_order() -> None:
    """Runtime routing candidates should reflect task fallback order."""

    fallbacks = config.get_task_fallbacks(ModelTask.EXTRACTION)
    candidates = config.get_model_candidates(ModelTask.EXTRACTION)
    assert candidates[: len(fallbacks)] == fallbacks
