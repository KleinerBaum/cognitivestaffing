"""Centralised model configuration and routing helpers."""

from __future__ import annotations

import logging
import os
import warnings
from dataclasses import dataclass
from enum import StrEnum
from typing import Dict, Mapping, Sequence

import streamlit as st

from constants.keys import StateKeys

logger = logging.getLogger("cognitive_needs.model_config")

# Canonical model identifiers as exposed by the OpenAI Responses API.
GPT4 = "gpt-4"
GPT4O = "gpt-4o"
GPT4O_MINI = "gpt-4o-mini"

GPT52 = "gpt-5.2"
GPT52_PRO = "gpt-5.2-pro"
GPT52_MINI = "gpt-5.2-mini"
GPT52_NANO = "gpt-5.2-nano"

GPT51 = "gpt-5"
GPT51_MINI = "gpt-5-mini"
GPT51_NANO = "gpt-5-nano"

GPT41_MINI = "gpt-4.1-mini"
GPT41_NANO = "gpt-4.1-nano"
O4_MINI = "o4-mini"
O3 = "o3"
O3_MINI = "o3-mini"
GPT35 = "gpt-3.5-turbo"

FAST = GPT51_NANO
QUALITY = GPT51_NANO
LONG_CONTEXT = GPT51_NANO
PRECISE = GPT51_NANO

EMBED_MODEL = "text-embedding-3-large"  # RAG

REASONING_LEVELS = ("none", "minimal", "low", "medium", "high")
_TRUTHY_ENV_VALUES: tuple[str, ...] = ("1", "true", "yes", "on")


def _is_truthy_flag(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in _TRUTHY_ENV_VALUES


LATEST_MODEL_ALIASES: tuple[tuple[str, str], ...] = (
    ("gpt-5.2-pro", GPT52_PRO),
    ("gpt-5.2-pro-latest", GPT52_PRO),
    ("gpt-5.2-mini", GPT52_MINI),
    ("gpt-5.2-mini-latest", GPT52_MINI),
    ("gpt-5.2-nano", GPT52_NANO),
    ("gpt-5.2-nano-latest", GPT52_NANO),
    ("gpt-5.2", GPT52),
    ("gpt-5.2-latest", GPT52),
    ("gpt-5-mini", GPT51_MINI),
    ("gpt-5-mini-latest", GPT51_MINI),
    ("gpt-5-nano", GPT51_NANO),
    ("gpt-5-nano-latest", GPT51_NANO),
    ("gpt-5.1-nano", GPT51_NANO),
    ("gpt-5.1-nano-latest", GPT51_NANO),
    ("gpt-5.1-mini", GPT51_MINI),
    ("gpt-5.1-mini-latest", GPT51_MINI),
    ("gpt-5.1", PRECISE),
    ("gpt-5.1-latest", PRECISE),
    ("gpt-5", GPT51),
    ("gpt-4.1-mini", GPT41_MINI),
    ("gpt-4.1-mini-latest", GPT41_MINI),
    ("gpt-4.1-nano", GPT41_NANO),
    ("gpt-4.1-nano-latest", GPT41_NANO),
    ("o4-mini", O4_MINI),
    ("o4-mini-latest", O4_MINI),
    ("o3-mini", O3_MINI),
    ("o3-mini-latest", O3_MINI),
    ("o3", O3),
    ("o3-latest", O3),
    ("gpt-4o-mini", GPT4O_MINI),
    ("gpt-4o-mini-latest", GPT4O_MINI),
    ("gpt-4o", GPT4O),
    ("gpt-4o-latest", GPT4O),
)

LEGACY_MODEL_ALIASES: tuple[tuple[str, str], ...] = (
    ("gpt-4o-mini-2024-08-06", GPT4O_MINI),
    ("gpt-4o-mini-2024-07-18", GPT4O_MINI),
    ("gpt-4o-mini-2024-05-13", GPT4O_MINI),
    ("gpt-4o-mini", GPT4O_MINI),
    ("gpt-4o-2024-08-06", GPT4O),
    ("gpt-4o-2024-05-13", GPT4O),
    ("gpt-4o", GPT4O),
)

MODEL_ALIASES: Dict[str, str] = {
    **{alias: target for alias, target in LATEST_MODEL_ALIASES},
    **{alias: target for alias, target in LEGACY_MODEL_ALIASES},
}

STRICT_NANO_ONLY = _is_truthy_flag(os.getenv("STRICT_NANO_ONLY"), default=True)

LIGHTWEIGHT_MODEL_DEFAULT = GPT51_NANO
MEDIUM_REASONING_MODEL_DEFAULT = GPT51_NANO
HIGH_REASONING_MODEL_DEFAULT = GPT51_NANO
REASONING_MODEL_DEFAULT = GPT51_NANO
PRIMARY_MODEL_DEFAULT = GPT51_NANO
PRIMARY_MODEL = PRIMARY_MODEL_DEFAULT

SUPPORTED_MODEL_CHOICES = {
    LIGHTWEIGHT_MODEL_DEFAULT,
    MEDIUM_REASONING_MODEL_DEFAULT,
    REASONING_MODEL_DEFAULT,
    GPT52,
    GPT52_PRO,
    GPT52_MINI,
    GPT52_NANO,
    GPT51_MINI,
    GPT51_NANO,
    GPT51,
    PRECISE,
    GPT41_NANO,
    GPT41_MINI,
    O3,
    O3_MINI,
    O4_MINI,
    GPT4O,
    GPT4O_MINI,
    GPT4,
    GPT35,
}


class ModelTask(StrEnum):
    """Known task categories for routing OpenAI calls."""

    DEFAULT = "default"
    EXTRACTION = "extraction"
    COMPANY_INFO = "company_info"
    FOLLOW_UP_QUESTIONS = "follow_up_questions"
    RAG_SUGGESTIONS = "rag_suggestions"
    SKILL_SUGGESTION = "skill_suggestion"
    BENEFIT_SUGGESTION = "benefit_suggestion"
    TASK_SUGGESTION = "task_suggestion"
    ONBOARDING_SUGGESTION = "onboarding_suggestion"
    JOB_AD = "job_ad"
    INTERVIEW_GUIDE = "interview_guide"
    PROFILE_SUMMARY = "profile_summary"
    CANDIDATE_MATCHING = "candidate_matching"
    DOCUMENT_REFINEMENT = "document_refinement"
    EXPLANATION = "explanation"
    SALARY_ESTIMATE = "salary_estimate"
    JSON_REPAIR = "json_repair"
    TEAM_ADVICE = "team_advice"
    PROGRESS_INBOX = "progress_inbox"


@dataclass(frozen=True)
class TaskModelConfig:
    """Configuration for a specific task including model preferences and capabilities."""

    model: str
    allow_json_schema: bool = True
    allow_response_format: bool = True


@dataclass(frozen=True)
class ModelCapabilities:
    """Capabilities for a concrete model identifier."""

    supports_json_schema: bool = True
    supports_response_format: bool = True


REASONING_EFFORT = "minimal"
LIGHTWEIGHT_MODEL = LIGHTWEIGHT_MODEL_DEFAULT
MEDIUM_REASONING_MODEL = MEDIUM_REASONING_MODEL_DEFAULT
HIGH_REASONING_MODEL = HIGH_REASONING_MODEL_DEFAULT
REASONING_MODEL = REASONING_MODEL_DEFAULT
DEFAULT_MODEL = PRIMARY_MODEL_DEFAULT
OPENAI_MODEL = PRIMARY_MODEL_DEFAULT

MODEL_ROUTING: Dict[str, str] = {}
MODEL_CONFIG: Dict[str, TaskModelConfig] = {}
TASK_MODEL_FALLBACKS: Dict[str, list[str]] = {}

_UNAVAILABLE_MODELS: set[str] = set()

_PRECISION_TASKS: frozenset[str] = frozenset({"reasoning"})
_LIGHTWEIGHT_TASKS: frozenset[str] = frozenset(
    {
        ModelTask.JSON_REPAIR.value,
        ModelTask.PROGRESS_INBOX.value,
        ModelTask.SALARY_ESTIMATE.value,
        "non_reasoning",
    }
)

PRIMARY_MODEL_CHOICES: tuple[str, ...] = (
    GPT51_MINI,
    GPT52,
    GPT52_PRO,
    GPT52_MINI,
    GPT52_NANO,
    GPT51,
    GPT51_NANO,
    GPT41_NANO,
    GPT4O_MINI,
    GPT4O,
    O3_MINI,
    O3,
    O4_MINI,
    GPT4,
    GPT41_MINI,
)


def normalise_reasoning_effort(value: str | None, *, default: str = "minimal") -> str:
    """Return a supported reasoning effort value or ``default`` when invalid."""

    if value is None:
        return default
    candidate = value.strip().lower()
    if not candidate:
        return default
    if candidate in REASONING_LEVELS:
        return candidate
    warnings.warn(
        "Unsupported REASONING_EFFORT '%s'; falling back to '%s'." % (candidate, default),
        RuntimeWarning,
    )
    return default


def requires_chat_completions(model: str | None) -> bool:
    """Return ``True`` when ``model`` must use the Chat Completions API."""

    normalised = normalise_model_name(model).lower()
    if not normalised:
        return False
    return normalised.startswith("gpt-3.5")


def normalise_model_name(value: str | None, *, prefer_latest: bool = True) -> str:
    """Return ``value`` with optional mapping of legacy aliases to current names."""

    if not value:
        return ""
    candidate = value.strip()
    if not candidate:
        return ""

    lowered = candidate.lower()
    if not prefer_latest:
        return candidate

    for alias, replacement in LATEST_MODEL_ALIASES:
        if lowered == alias or lowered.startswith(f"{alias}-"):
            return replacement

    for legacy, replacement in LEGACY_MODEL_ALIASES:
        if lowered == legacy or lowered.startswith(f"{legacy}-"):
            return replacement

    for alias, replacement in MODEL_ALIASES.items():
        lowered_alias = alias.lower()
        if lowered == lowered_alias or lowered.startswith(f"{lowered_alias}-"):
            return replacement

    if lowered.startswith("gpt-4.1-mini"):
        return GPT41_MINI
    if lowered.startswith("gpt-4.1-nano"):
        return GPT41_NANO
    if lowered.startswith("gpt-5.2-pro"):
        return GPT52_PRO
    if lowered.startswith("gpt-5.2-mini"):
        return GPT52_MINI
    if lowered.startswith("gpt-5.2-nano"):
        return GPT52_NANO
    if lowered.startswith("gpt-5.2"):
        return GPT52
    if lowered.startswith("gpt-5.1-mini"):
        return GPT51_MINI
    if lowered.startswith("gpt-5.1-nano"):
        return GPT51_NANO
    if lowered.startswith("gpt-5.1"):
        return PRECISE
    if lowered.startswith("gpt-5-mini"):
        return GPT51_MINI
    if lowered.startswith("gpt-5-nano"):
        return GPT51_NANO
    if lowered.startswith("gpt-5"):
        return GPT51
    if lowered.startswith("o4-mini"):
        return O4_MINI
    if lowered.startswith("o3-mini"):
        return O3_MINI
    if lowered.startswith("o3"):
        return O3
    if lowered.startswith("gpt-4o-mini"):
        return GPT4O_MINI
    if lowered.startswith("gpt-4o"):
        return GPT4O
    return candidate


def _canonical_model_name(value: str | None) -> str:
    """Return a lower-cased identifier suitable for availability tracking."""

    if not value:
        return ""
    return value.strip().lower()


_MODEL_CAPABILITY_OVERRIDES: dict[str, ModelCapabilities] = {
    _canonical_model_name(GPT35): ModelCapabilities(
        supports_json_schema=False,
        supports_response_format=False,
    )
}


def resolve_supported_model(value: str | None, fallback: str) -> str:
    """Normalise overrides to supported defaults with graceful degradation."""

    if not value:
        return fallback
    candidate = normalise_model_name(value)
    if candidate in SUPPORTED_MODEL_CHOICES or candidate == EMBED_MODEL:
        return candidate
    if candidate:
        warnings.warn(
            "Unsupported default model '%s'; falling back to '%s'." % (candidate, fallback),
            RuntimeWarning,
        )
    return fallback


def _enforce_strict_generation_model(model: str, *, source: str) -> str:
    normalised = normalise_model_name(model) or model
    if STRICT_NANO_ONLY and normalised != GPT51_NANO:
        warnings.warn(
            "STRICT_NANO_ONLY enabled: forcing %s from '%s' to '%s'." % (source, normalised, GPT51_NANO),
            RuntimeWarning,
        )
        return GPT51_NANO
    return normalised


def _resolve_generation_model(value: str | None, fallback: str, *, source: str) -> str:
    resolved = resolve_supported_model(value, fallback)
    return _enforce_strict_generation_model(resolved, source=source)


def _model_for_reasoning_level(level: str) -> str:
    """Return the preferred model for ``level`` of reasoning effort."""

    mapping = {
        "none": LIGHTWEIGHT_MODEL,
        "minimal": LIGHTWEIGHT_MODEL,
        "low": LIGHTWEIGHT_MODEL,
        "medium": MEDIUM_REASONING_MODEL,
        "high": HIGH_REASONING_MODEL,
    }
    return mapping.get(level, HIGH_REASONING_MODEL)


def _prefer_lightweight(task: str) -> bool:
    return task in _LIGHTWEIGHT_TASKS and task not in _PRECISION_TASKS


def _build_model_config(overrides: Mapping[str, str] | None) -> Dict[str, TaskModelConfig]:
    config: Dict[str, TaskModelConfig] = {
        ModelTask.DEFAULT.value: TaskModelConfig(model=OPENAI_MODEL),
        ModelTask.EXTRACTION.value: TaskModelConfig(model=LIGHTWEIGHT_MODEL),
        ModelTask.COMPANY_INFO.value: TaskModelConfig(model=LIGHTWEIGHT_MODEL),
        ModelTask.FOLLOW_UP_QUESTIONS.value: TaskModelConfig(
            model=REASONING_MODEL,
            allow_json_schema=True,
            allow_response_format=True,
        ),
        ModelTask.RAG_SUGGESTIONS.value: TaskModelConfig(model=REASONING_MODEL),
        ModelTask.SKILL_SUGGESTION.value: TaskModelConfig(model=REASONING_MODEL),
        ModelTask.BENEFIT_SUGGESTION.value: TaskModelConfig(model=REASONING_MODEL),
        ModelTask.TASK_SUGGESTION.value: TaskModelConfig(model=REASONING_MODEL),
        ModelTask.ONBOARDING_SUGGESTION.value: TaskModelConfig(model=REASONING_MODEL),
        ModelTask.JOB_AD.value: TaskModelConfig(model=REASONING_MODEL),
        ModelTask.INTERVIEW_GUIDE.value: TaskModelConfig(model=REASONING_MODEL),
        ModelTask.PROFILE_SUMMARY.value: TaskModelConfig(model=REASONING_MODEL),
        ModelTask.CANDIDATE_MATCHING.value: TaskModelConfig(model=REASONING_MODEL),
        ModelTask.DOCUMENT_REFINEMENT.value: TaskModelConfig(model=LONG_CONTEXT),
        ModelTask.EXPLANATION.value: TaskModelConfig(model=REASONING_MODEL),
        ModelTask.SALARY_ESTIMATE.value: TaskModelConfig(model=LIGHTWEIGHT_MODEL),
        ModelTask.TEAM_ADVICE.value: TaskModelConfig(
            model=REASONING_MODEL,
            allow_json_schema=False,
            allow_response_format=False,
        ),
        ModelTask.JSON_REPAIR.value: TaskModelConfig(model=LIGHTWEIGHT_MODEL),
        ModelTask.PROGRESS_INBOX.value: TaskModelConfig(model=LIGHTWEIGHT_MODEL),
        "embedding": TaskModelConfig(
            model=EMBED_MODEL,
            allow_json_schema=False,
            allow_response_format=False,
        ),
        "non_reasoning": TaskModelConfig(model=LIGHTWEIGHT_MODEL),
        "reasoning": TaskModelConfig(model=REASONING_MODEL),
    }
    if overrides:
        default_fallback = config.get(ModelTask.DEFAULT.value, TaskModelConfig(DEFAULT_MODEL)).model
        for override_key, override_value in overrides.items():
            base = config.get(override_key)
            fallback = base.model if base else default_fallback
            config[override_key] = TaskModelConfig(
                model=(
                    resolve_supported_model(override_value, fallback)
                    if override_key == "embedding"
                    else _resolve_generation_model(override_value, fallback, source=f"MODEL_ROUTING__{override_key}")
                ),
                allow_json_schema=base.allow_json_schema if base else True,
                allow_response_format=base.allow_response_format if base else True,
            )
    normalised: Dict[str, TaskModelConfig] = {}
    for key, task_config in config.items():
        if key == "embedding":
            normalised[key] = task_config
            continue
        model_name = normalise_model_name(task_config.model) or task_config.model
        if STRICT_NANO_ONLY:
            model_name = _enforce_strict_generation_model(model_name, source="task '%s'" % key)
        normalised[key] = TaskModelConfig(
            model=model_name,
            allow_json_schema=task_config.allow_json_schema,
            allow_response_format=task_config.allow_response_format,
        )
    return normalised


MODEL_FALLBACKS: Dict[str, list[str]] = {
    _canonical_model_name(GPT52_PRO): [GPT52_PRO, O3, O3_MINI, GPT4O, GPT4O_MINI, GPT4, GPT35],
    _canonical_model_name(GPT52): [GPT52, O3_MINI, GPT4O, GPT4O_MINI, GPT4, GPT35],
    _canonical_model_name(GPT52_MINI): [GPT52_MINI, GPT4O, GPT4O_MINI, O3_MINI, GPT4, GPT35],
    _canonical_model_name(GPT52_NANO): [GPT52_NANO, GPT4O_MINI, GPT4O, GPT41_MINI, GPT4, GPT35],
    _canonical_model_name(PRECISE): [PRECISE, O4_MINI, GPT4O, GPT4O_MINI, GPT41_MINI, GPT4, GPT35],
    _canonical_model_name(GPT51): [GPT51, O3_MINI, GPT4O, GPT4O_MINI, GPT41_MINI, GPT4, GPT35],
    _canonical_model_name(GPT51_MINI): [GPT51_MINI, GPT4O, GPT4O_MINI, O3_MINI, GPT41_MINI, GPT4, GPT35],
    _canonical_model_name(GPT51_NANO): [GPT51_NANO, GPT4O_MINI, GPT4O, GPT41_MINI, GPT4, GPT35],
    _canonical_model_name(GPT41_NANO): [GPT41_NANO, GPT41_MINI, GPT4O_MINI, GPT4O, O3_MINI, GPT4, GPT35],
    _canonical_model_name(O3): [O3, O3_MINI, O4_MINI, GPT4O, GPT4O_MINI, GPT4, GPT35],
    _canonical_model_name(O3_MINI): [O3_MINI, O4_MINI, GPT4O, GPT4O_MINI, GPT41_MINI, GPT4, GPT35],
    _canonical_model_name(O4_MINI): [O4_MINI, O3_MINI, GPT4O, GPT4O_MINI, GPT41_MINI, GPT4, GPT35],
    _canonical_model_name(GPT4O_MINI): [GPT4O_MINI, GPT4O, O3_MINI, O4_MINI, GPT41_MINI, GPT4, GPT35],
    _canonical_model_name(GPT4O): [GPT4O, GPT4O_MINI, O3_MINI, O4_MINI, GPT41_MINI, GPT4, GPT35],
    _canonical_model_name(GPT4): [GPT4, GPT4O, GPT4O_MINI, GPT41_MINI, O3_MINI, GPT35],
    _canonical_model_name(GPT35): [GPT35, GPT4O_MINI, GPT4O, GPT41_MINI, GPT4],
}


def get_task_fallbacks(task: ModelTask | str) -> list[str]:
    """Return task fallbacks with schema-capable models prioritised first."""

    ordered = get_model_fallbacks_for(task)
    structured_chain = [model_name for model_name in ordered if get_model_capabilities(model_name).supports_json_schema]
    text_only_chain = [model_name for model_name in ordered if model_name not in structured_chain]
    return [*structured_chain, *text_only_chain]


def _merge_chains(primary: Sequence[str], secondary: Sequence[str]) -> list[str]:
    """Return ``primary`` + ``secondary`` with duplicates removed preserving order."""

    merged: list[str] = []
    for chain in (primary, secondary):
        for item in chain:
            if item and item not in merged:
                merged.append(item)
    return merged


def _build_task_fallbacks() -> Dict[str, list[str]]:
    mapping: Dict[str, list[str]] = {}
    for task, model_name in MODEL_ROUTING.items():
        if task == "embedding":
            mapping[task] = [model_name]
            continue
        preferred = model_name or OPENAI_MODEL or LIGHTWEIGHT_MODEL_DEFAULT
        if STRICT_NANO_ONLY:
            mapping[task] = [GPT51_NANO]
            continue
        canonical = _canonical_model_name(preferred)
        fallbacks = MODEL_FALLBACKS.get(canonical, [preferred])
        options: list[str] = []
        for candidate in [preferred, *fallbacks]:
            if candidate and candidate not in options:
                options.append(candidate)
        mapping[task] = options
    return mapping


def configure_models(
    *,
    reasoning_effort: str,
    lightweight_override: str | None = None,
    medium_reasoning_override: str | None = None,
    high_reasoning_override: str | None = None,
    primary_override: str | None = None,
    default_override: str | None = None,
    openai_override: str | None = None,
    model_routing_overrides: Mapping[str, str] | None = None,
    strict_nano_only: bool | None = None,
) -> None:
    """Initialise model defaults, routing, and fallbacks."""

    global REASONING_EFFORT, LIGHTWEIGHT_MODEL, MEDIUM_REASONING_MODEL, HIGH_REASONING_MODEL
    global \
        REASONING_MODEL, \
        DEFAULT_MODEL, \
        OPENAI_MODEL, \
        MODEL_ROUTING, \
        MODEL_CONFIG, \
        TASK_MODEL_FALLBACKS, \
        PRIMARY_MODEL, \
        STRICT_NANO_ONLY

    clear_unavailable_models()
    if strict_nano_only is not None:
        STRICT_NANO_ONLY = bool(strict_nano_only)
    REASONING_EFFORT = normalise_reasoning_effort(reasoning_effort, default=REASONING_EFFORT)
    LIGHTWEIGHT_MODEL = _resolve_generation_model(
        lightweight_override,
        LIGHTWEIGHT_MODEL_DEFAULT,
        source="LIGHTWEIGHT_MODEL",
    )
    MEDIUM_REASONING_MODEL = _resolve_generation_model(
        medium_reasoning_override,
        MEDIUM_REASONING_MODEL_DEFAULT,
        source="MEDIUM_REASONING_MODEL",
    )
    HIGH_REASONING_MODEL = _resolve_generation_model(
        high_reasoning_override,
        HIGH_REASONING_MODEL_DEFAULT,
        source="HIGH_REASONING_MODEL",
    )
    PRIMARY_MODEL = _resolve_generation_model(primary_override, PRIMARY_MODEL_DEFAULT, source="PRIMARY_MODEL")
    DEFAULT_MODEL = _resolve_generation_model(default_override, PRIMARY_MODEL, source="DEFAULT_MODEL")
    OPENAI_MODEL = _resolve_generation_model(openai_override, DEFAULT_MODEL, source="OPENAI_MODEL")
    REASONING_MODEL = _model_for_reasoning_level(REASONING_EFFORT)
    logger.info(
        "Configured model defaults: reasoning_effort='%s', primary_model='%s'.",
        REASONING_EFFORT,
        PRIMARY_MODEL,
    )
    MODEL_CONFIG = _build_model_config(model_routing_overrides)
    MODEL_ROUTING = {task: task_config.model for task, task_config in MODEL_CONFIG.items()}
    TASK_MODEL_FALLBACKS = _build_task_fallbacks()


def clear_unavailable_models(*models: str) -> None:
    """Remove ``models`` from the unavailable cache or reset it entirely."""

    if not models:
        _UNAVAILABLE_MODELS.clear()
        return
    for model in models:
        canonical = _canonical_model_name(model)
        if canonical:
            _UNAVAILABLE_MODELS.discard(canonical)


def mark_model_unavailable(model: str) -> None:
    """Remember that ``model`` cannot be used for subsequent requests."""

    canonical = _canonical_model_name(model)
    if canonical:
        _UNAVAILABLE_MODELS.add(canonical)


def is_model_available(model: str) -> bool:
    """Return ``True`` if ``model`` has not been marked as unavailable."""

    canonical = _canonical_model_name(model)
    if not canonical:
        return False
    return canonical not in _UNAVAILABLE_MODELS


def get_model_capabilities(model: str | None) -> ModelCapabilities:
    """Return capability flags for ``model`` with sane defaults."""

    canonical = _canonical_model_name(normalise_model_name(model) or model)
    if not canonical:
        return ModelCapabilities()
    if canonical.startswith("gpt-3.5"):
        return ModelCapabilities(
            supports_json_schema=False,
            supports_response_format=False,
        )
    return _MODEL_CAPABILITY_OVERRIDES.get(canonical, ModelCapabilities())


def get_model_fallbacks_for(task: ModelTask | str) -> list[str]:
    """Return the fallback chain configured for ``task`` without overrides."""

    key = task.value if isinstance(task, ModelTask) else str(task)
    fallback_chain = TASK_MODEL_FALLBACKS.get(key)
    if fallback_chain is not None:
        return list(fallback_chain)
    return list(
        TASK_MODEL_FALLBACKS.get(
            ModelTask.DEFAULT.value,
            [PRIMARY_MODEL, GPT51_NANO] if STRICT_NANO_ONLY else [PRIMARY_MODEL, GPT4O, GPT35, GPT52_MINI, GPT52],
        )
    )


def get_task_config(task: ModelTask | str) -> TaskModelConfig:
    """Return the configuration entry for ``task`` with a safe default."""

    key = task.value if isinstance(task, ModelTask) else str(task).strip().lower()
    if not key:
        key = ModelTask.DEFAULT.value
    task_config = MODEL_CONFIG.get(key)
    if task_config:
        return task_config
    default_config = MODEL_CONFIG.get(ModelTask.DEFAULT.value)
    if default_config:
        return default_config
    raise KeyError(f"No model configuration available for task '{task}'.")


def normalise_model_override(value: object) -> str | None:
    """Normalize manual model override values."""

    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if not candidate:
        return None
    if candidate.lower() in {"auto", "automatic", "default"}:
        return None
    return normalise_model_name(candidate)


def _get_reasoning_mode() -> str:
    """Return the active reasoning mode (``quick`` or ``precise``)."""

    try:
        raw_mode = st.session_state.get(StateKeys.REASONING_MODE)
    except Exception:  # pragma: no cover - Streamlit session not initialised
        raw_mode = None
    if isinstance(raw_mode, str):
        mode_value = raw_mode.strip().lower()
        if mode_value in {"quick", "fast", "schnell"}:
            return "quick"
        if mode_value in {"precise", "precision", "genau", "präzise"}:
            return "precise"
    try:
        effort_value = st.session_state.get(StateKeys.REASONING_EFFORT, REASONING_EFFORT)
    except Exception:  # pragma: no cover - Streamlit session not initialised
        effort_value = REASONING_EFFORT
    if isinstance(effort_value, str) and effort_value.strip().lower() in {"none", "minimal", "low"}:
        return "quick"
    return "precise"


def get_reasoning_mode() -> str:
    """Public helper exposing the active reasoning mode."""

    return _get_reasoning_mode()


def _collect_candidate_models(task: ModelTask | str, override: str | None) -> list[str]:
    """Assemble model candidates for ``task`` including manual overrides."""

    candidates: list[str] = []

    if isinstance(task, ModelTask):
        task_key = task.value
    else:
        task_key = str(task).strip().lower()

    def _extend_with_model_chain(model_name: str) -> None:
        canonical = _canonical_model_name(model_name)
        if not canonical:
            return
        if STRICT_NANO_ONLY:
            return
        chain = MODEL_FALLBACKS.get(canonical)
        if not chain:
            return
        for fallback in chain[1:]:
            if fallback and fallback not in candidates:
                candidates.append(fallback)

    if override:
        override_name = normalise_model_name(override, prefer_latest=False) or override.strip()
        if override_name:
            candidates.append(override_name)
            _extend_with_model_chain(override_name)
    fallback_chain = get_task_fallbacks(task)
    mode = _get_reasoning_mode() if task_key != ModelTask.DEFAULT.value else None
    if mode == "quick" and _prefer_lightweight(task_key):
        lightweight_chain = MODEL_FALLBACKS.get(
            _canonical_model_name(LIGHTWEIGHT_MODEL),
            [LIGHTWEIGHT_MODEL],
        )
        fallback_chain = _merge_chains(lightweight_chain, fallback_chain)
    elif (
        mode == "precise"
        and task_key not in {"embedding", "non_reasoning", "reasoning"}
        and not _prefer_lightweight(task_key)
    ):
        reasoning_chain = MODEL_FALLBACKS.get(
            _canonical_model_name(REASONING_MODEL),
            [REASONING_MODEL],
        )
        fallback_chain = _merge_chains(reasoning_chain, fallback_chain)
    for candidate in fallback_chain:
        if candidate and candidate not in candidates:
            candidates.append(candidate)
    return candidates


def get_model_candidates(task: ModelTask | str, *, override: str | None = None) -> list[str]:
    """Return ordered model candidates for ``task`` including overrides."""

    return _collect_candidate_models(task, override)


def get_first_available_model(task: ModelTask | str, *, override: str | None = None) -> str:
    """Return the first available model for ``task`` using the configured fallbacks."""

    candidates = _collect_candidate_models(task, override)
    logger = logging.getLogger("cognitive_needs.model_routing")
    attempted: list[str] = []
    for candidate in candidates:
        attempted.append(candidate)
        if is_model_available(candidate):
            if len(attempted) > 1:
                logger.warning(
                    "Model routing fallback for task '%s': unavailable candidates %s → using '%s'.",
                    task,
                    ", ".join(attempted[:-1]),
                    candidate,
                )
            return candidate
    if candidates:
        logger.warning(
            "All configured models unavailable for task '%s'; using last candidate '%s'.",
            task,
            candidates[-1],
        )
        return candidates[-1]
    fallback_model = GPT51_NANO if STRICT_NANO_ONLY else GPT41_MINI
    logger.error("No model candidates resolved for task '%s'; falling back to %s.", task, fallback_model)
    return fallback_model


def get_model_for(task: ModelTask | str, *, override: str | None = None) -> str:
    """Return the configured model for ``task`` respecting manual overrides."""

    return get_first_available_model(task, override=override)


def select_model(task_type: ModelTask | str | None, *, override: str | None = None) -> str:
    """Return the preferred model for ``task_type`` or fallback to defaults.

    The helper understands both :class:`ModelTask` members and shorthand labels
    (``"non_reasoning"``/``"reasoning"``) so callers that only care about the
    reasoning tier can rely on a single entry point.
    """  # REASONING_SELECTOR

    if task_type is None:
        return get_model_for(ModelTask.DEFAULT, override=override)
    if isinstance(task_type, ModelTask):
        return get_model_for(task_type, override=override)

    key = str(task_type).strip().lower() or ModelTask.DEFAULT.value
    return get_model_for(key, override=override)


def get_model_candidates_for_ui() -> tuple[str | None, ...]:
    """Return the primary model options for UI selectors."""

    return (None, *PRIMARY_MODEL_CHOICES)
