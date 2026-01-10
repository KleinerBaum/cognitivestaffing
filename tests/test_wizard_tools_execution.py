"""Tests for the wizard execution helper tools."""

from __future__ import annotations

import json
import sys
from pathlib import Path
import types

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

if "agents" not in sys.modules:
    agents_stub = types.ModuleType("agents")

    def _function_tool(func):  # type: ignore[return-type]
        return func

    agents_stub.function_tool = _function_tool  # type: ignore[attr-defined]
    sys.modules["agents"] = agents_stub

import config.models as model_config
from wizard_tools.experimental import execution


@pytest.fixture(autouse=True)
def reset_execution_state() -> None:
    """Provide a clean execution state for every test."""

    execution._reset_state_for_tests()
    yield
    execution._reset_state_for_tests()


def test_run_stage_tracks_attempts_and_config() -> None:
    first = json.loads(execution.run_stage("stage.alpha", {"foo": "bar"}))
    assert first["outputs"]["attempt"] == 1
    assert first["inputs"] == {"foo": "bar"}
    assert first["config"]["model"] == model_config.OPENAI_MODEL

    second = json.loads(execution.run_stage("stage.alpha"))
    assert second["outputs"]["attempt"] == 2


def test_retry_stage_uses_strategy_and_config() -> None:
    payload = json.loads(execution.retry_stage("retry-stage", "regenerate"))

    assert payload["strategy"] == "regenerate"
    assert payload["attempt"] == 1
    assert payload["config"]["model"] == model_config.OPENAI_MODEL


def test_stage_specific_model_override() -> None:
    global_run = json.loads(execution.run_stage("stage-global"))
    assert global_run["config"]["model"] == model_config.OPENAI_MODEL

    execution.set_model("stage-global", model_config.O4_MINI)
    stage_run = json.loads(execution.run_stage("stage-global"))
    assert stage_run["config"]["model"] == model_config.O4_MINI

    other_run = json.loads(execution.run_stage("other-stage"))
    assert other_run["config"]["model"] == model_config.OPENAI_MODEL


def test_set_model_reports_locked_state() -> None:
    payload = json.loads(execution.set_model(None, model_config.GPT4O))

    assert payload["locked"] is True
    assert payload["model"] == model_config.OPENAI_MODEL


def test_set_temperature_validation() -> None:
    with pytest.raises(ValueError):
        execution.set_temperature(None, -0.1)
    with pytest.raises(ValueError):
        execution.set_temperature(None, 2.1)

    execution.set_temperature("temp-stage", 1.5)
    payload = json.loads(execution.run_stage("temp-stage"))
    assert payload["config"]["temperature"] == 1.5

    global_payload = json.loads(execution.run_stage("other-stage"))
    assert global_payload["config"]["temperature"] == 0.2


def test_set_max_output_tokens_validation() -> None:
    with pytest.raises(ValueError):
        execution.set_max_output_tokens(None, 0)

    execution.set_max_output_tokens("tokens-stage", 1024)
    payload = json.loads(execution.run_stage("tokens-stage"))
    assert payload["config"]["max_output_tokens"] == 1024

    default_payload = json.loads(execution.run_stage("default-stage"))
    assert default_payload["config"]["max_output_tokens"] == 1024


def test_run_all_reports_summary() -> None:
    execution.run_stage("stage-1")
    execution.retry_stage("stage-1", "regenerate")
    execution.run_stage("stage-2", {"a": 1})

    summary = json.loads(execution.run_all("vacancy-42"))

    assert summary["vacancy_id"] == "vacancy-42"
    assert summary["completed"] is True
    assert summary["stages_run"] == ["stage-1", "stage-2"]
    assert summary["total_attempts"] == 3
