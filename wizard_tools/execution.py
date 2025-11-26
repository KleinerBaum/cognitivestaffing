"""Execution control utilities for the wizard graph."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass, replace
from typing import Any, Dict, List, Literal, Optional

from agents import function_tool

ModelName = Literal[
    "gpt-5.1",
    "gpt-5.1-mini",
    "gpt-5.1-nano",
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4.1-mini",
    "gpt-4.1-nano",
    "o4-mini",
    "o3",
    "o3-mini",
]
ReasoningEffort = Literal["minimal", "medium", "high"]
ToolChoiceMode = Literal["auto", "none", "force"]
RetryStrategy = Literal["same_inputs", "regenerate", "raise_effort"]


@dataclass
class StageRuntimeConfig:
    """Configuration that influences how a stage is executed."""

    model: ModelName = "gpt-5.1-mini"
    reasoning_effort: ReasoningEffort = "minimal"
    tool_choice_mode: ToolChoiceMode = "auto"
    tool_choice_function_name: Optional[str] = None
    temperature: float = 0.2
    max_output_tokens: int = 2048

    def to_payload(self) -> Dict[str, Any]:
        """Return a JSON-serialisable view of the configuration."""

        return {
            "model": self.model,
            "reasoning_effort": self.reasoning_effort,
            "tool_choice_mode": self.tool_choice_mode,
            "tool_choice_function_name": self.tool_choice_function_name,
            "temperature": self.temperature,
            "max_output_tokens": self.max_output_tokens,
        }


@dataclass
class StageRunRecord:
    """Snapshot of a single stage execution attempt."""

    stage_id: str
    attempt: int
    inputs: Dict[str, Any]
    outputs: Dict[str, Any]
    reasoning_summary: str
    config: StageRuntimeConfig
    strategy: Optional[RetryStrategy] = None

    def to_payload(self) -> Dict[str, Any]:
        """Return a JSON-serialisable payload describing the run."""

        payload: Dict[str, Any] = {
            "stage_id": self.stage_id,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "reasoning_summary": self.reasoning_summary,
            "attempt": self.attempt,
            "config": self.config.to_payload(),
        }
        if self.strategy is not None:
            payload["strategy"] = self.strategy
        return payload


class _ExecutionState:
    """Mutable execution state used across tool invocations."""

    def __init__(self) -> None:
        self._global_config = StageRuntimeConfig()
        self._stage_configs: Dict[str, StageRuntimeConfig] = {}
        self._stage_attempts: Dict[str, int] = {}
        self._stage_history: Dict[str, List[StageRunRecord]] = {}
        self._completed_vacancies: set[str] = set()

    def reset(self) -> None:
        """Reset the state – primarily used by the test-suite."""

        self._global_config = StageRuntimeConfig()
        self._stage_configs.clear()
        self._stage_attempts.clear()
        self._stage_history.clear()
        self._completed_vacancies.clear()

    def _mutable_config(self, stage_id: Optional[str]) -> StageRuntimeConfig:
        if stage_id is None:
            return self._global_config
        config = self._stage_configs.get(stage_id)
        if config is None:
            config = replace(self._global_config)
            self._stage_configs[stage_id] = config
        return config

    def _resolved_config(self, stage_id: Optional[str]) -> StageRuntimeConfig:
        if stage_id is None:
            return replace(self._global_config)
        config = self._stage_configs.get(stage_id) or self._global_config
        return replace(config)

    def run_stage(self, stage_id: str, inputs: Dict[str, Any]) -> StageRunRecord:
        attempt = self._stage_attempts.get(stage_id, 0) + 1
        self._stage_attempts[stage_id] = attempt
        config = self._resolved_config(stage_id)
        outputs = {"ok": True, "attempt": attempt}
        record = StageRunRecord(
            stage_id=stage_id,
            attempt=attempt,
            inputs=deepcopy(inputs),
            outputs=outputs,
            reasoning_summary="Executed.",
            config=config,
        )
        self._stage_history.setdefault(stage_id, []).append(record)
        return record

    def retry_stage(self, stage_id: str, strategy: RetryStrategy) -> StageRunRecord:
        attempt = self._stage_attempts.get(stage_id, 0) + 1
        self._stage_attempts[stage_id] = attempt
        config = self._resolved_config(stage_id)
        outputs = {"retried": True, "strategy": strategy, "attempt": attempt}
        record = StageRunRecord(
            stage_id=stage_id,
            attempt=attempt,
            inputs={"strategy": strategy},
            outputs=outputs,
            reasoning_summary=f"Retry with strategy '{strategy}'.",
            config=config,
            strategy=strategy,
        )
        self._stage_history.setdefault(stage_id, []).append(record)
        return record

    def run_all(self, vacancy_id: str) -> Dict[str, Any]:
        self._completed_vacancies.add(vacancy_id)
        stages_run = sorted(self._stage_history.keys())
        total_attempts = sum(len(records) for records in self._stage_history.values())
        return {
            "vacancy_id": vacancy_id,
            "completed": True,
            "stages_run": stages_run,
            "total_attempts": total_attempts,
        }

    def set_model(self, stage_id: Optional[str], model: ModelName) -> StageRuntimeConfig:
        config = self._mutable_config(stage_id)
        config.model = model
        return self._resolved_config(stage_id)

    def set_reasoning_effort(self, stage_id: Optional[str], level: ReasoningEffort) -> StageRuntimeConfig:
        config = self._mutable_config(stage_id)
        config.reasoning_effort = level
        return self._resolved_config(stage_id)

    def set_tool_choice(
        self,
        stage_id: Optional[str],
        mode: ToolChoiceMode,
        function_name: Optional[str],
    ) -> StageRuntimeConfig:
        config = self._mutable_config(stage_id)
        config.tool_choice_mode = mode
        config.tool_choice_function_name = function_name if mode == "force" else None
        return self._resolved_config(stage_id)

    def set_temperature(self, stage_id: Optional[str], value: float) -> StageRuntimeConfig:
        if not 0 <= value <= 2:
            raise ValueError("temperature must be between 0 and 2 inclusive")
        config = self._mutable_config(stage_id)
        config.temperature = value
        return self._resolved_config(stage_id)

    def set_max_output_tokens(self, stage_id: Optional[str], value: int) -> StageRuntimeConfig:
        if value <= 0:
            raise ValueError("max_output_tokens must be greater than zero")
        config = self._mutable_config(stage_id)
        config.max_output_tokens = value
        return self._resolved_config(stage_id)


_STATE = _ExecutionState()


def _response(payload: Dict[str, Any]) -> str:
    return json.dumps(payload)


@function_tool
def run_stage(stage_id: str, inputs: Optional[Dict[str, Any]] = None) -> str:
    """Execute the stage’s domain op."""

    record = _STATE.run_stage(stage_id, inputs or {})
    return _response(record.to_payload())


@function_tool
def run_all(vacancy_id: str) -> str:
    """Run all stages topologically."""

    summary = _STATE.run_all(vacancy_id)
    return _response(summary)


@function_tool
def retry_stage(stage_id: str, strategy: RetryStrategy = "regenerate") -> str:
    """Retry a failed or low-confidence stage."""

    record = _STATE.retry_stage(stage_id, strategy)
    payload = {
        "stage_id": stage_id,
        "retried": True,
        "strategy": strategy,
        "attempt": record.attempt,
        "config": record.config.to_payload(),
    }
    return _response(payload)


@function_tool
def set_model(stage_id: Optional[str], model: ModelName) -> str:
    """Set model for a stage or globally."""

    config = _STATE.set_model(stage_id, model)
    payload = {
        "ok": True,
        "stage_id": stage_id,
        "model": config.model,
        "scope": "global" if stage_id is None else "stage",
    }
    return _response(payload)


@function_tool
def set_reasoning_effort(stage_id: Optional[str], level: ReasoningEffort = "minimal") -> str:
    """Set GPT-5 reasoning effort for a stage or globally."""

    config = _STATE.set_reasoning_effort(stage_id, level)
    payload = {
        "ok": True,
        "stage_id": stage_id,
        "level": config.reasoning_effort,
        "scope": "global" if stage_id is None else "stage",
    }
    return _response(payload)


@function_tool
def set_tool_choice(
    stage_id: Optional[str],
    mode: ToolChoiceMode = "auto",
    function_name: Optional[str] = None,
) -> str:
    """Control tool selection."""

    config = _STATE.set_tool_choice(stage_id, mode, function_name)
    payload = {
        "ok": True,
        "stage_id": stage_id,
        "mode": config.tool_choice_mode,
        "function_name": config.tool_choice_function_name,
        "scope": "global" if stage_id is None else "stage",
    }
    return _response(payload)


@function_tool
def set_temperature(stage_id: Optional[str], value: float = 0.2) -> str:
    """Set sampling temperature (0..2)."""

    config = _STATE.set_temperature(stage_id, value)
    payload = {
        "ok": True,
        "stage_id": stage_id,
        "temperature": config.temperature,
        "scope": "global" if stage_id is None else "stage",
    }
    return _response(payload)


@function_tool
def set_max_output_tokens(stage_id: Optional[str], value: int = 2048) -> str:
    """Cap output tokens for a stage or globally."""

    config = _STATE.set_max_output_tokens(stage_id, value)
    payload = {
        "ok": True,
        "stage_id": stage_id,
        "max_output_tokens": config.max_output_tokens,
        "scope": "global" if stage_id is None else "stage",
    }
    return _response(payload)


def _reset_state_for_tests() -> None:
    """Reset module state; intended for use in unit tests."""

    _STATE.reset()


__all__ = [
    "retry_stage",
    "run_all",
    "run_stage",
    "set_max_output_tokens",
    "set_model",
    "set_reasoning_effort",
    "set_temperature",
    "set_tool_choice",
]
