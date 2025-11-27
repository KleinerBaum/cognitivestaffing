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
    [ModelTask.FOLLOW_UP_QUESTIONS, ModelTask.TEAM_ADVICE],
)
def test_text_only_tasks_disable_json(task: ModelTask) -> None:
    """Certain conversational tasks must avoid JSON and response-formatting."""

    config_entry = get_task_config(task)
    assert config_entry.allow_json_schema is False
    assert config_entry.allow_response_format is False


@pytest.mark.parametrize(
    "task",
    [ModelTask.EXTRACTION, ModelTask.JSON_REPAIR],
)
def test_json_tasks_allow_schema(task: ModelTask) -> None:
    """Structured tasks should keep JSON schema and response formatting enabled."""

    config_entry = get_task_config(task)
    assert config_entry.allow_json_schema is True
    assert config_entry.allow_response_format is True
