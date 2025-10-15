"""Central configuration for the Cognitive Needs Responses API client.

The application now routes requests between OpenAI's GPT-5 family to balance
quality and cost. ``gpt-5.1-mini`` (GPT-5 mini) serves as the default large
language model for generative workloads, while ``gpt-5.1-nano`` (GPT-5 nano)
powers lightweight suggestion flows.
Structured retrieval now standardises on ``text-embedding-3-large`` (3,072
dimensions) for higher-fidelity RAG vectors.

Set ``DEFAULT_MODEL`` or ``OPENAI_MODEL`` to override the primary model and use
``REASONING_EFFORT`` (``minimal`` | ``low`` | ``medium`` | ``high``) to control
how much reasoning the model performs by default.
"""

import logging
import os
import warnings

import streamlit as st
from enum import StrEnum
from typing import Dict

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


EMBED_MODEL = "text-embedding-3-large"  # RAG
STRICT_JSON = True
CHUNK_TOKENS = 600
CHUNK_OVERLAP = 0.1


# Canonical GPT-5 model identifiers as exposed by the OpenAI API.
#
# OpenAI's public documentation describes the "GPT-5" tiers as "GPT-5", "GPT-5
# mini" and "GPT-5 nano". The actual API endpoints follow the ``gpt-5.1-*``
# naming pattern (with dated suffices such as ``-latest`` or a concrete release
# date). ``normalise_model_name`` below maps historic aliases to these
# canonical identifiers so the rest of the application only sees the official
# names.
GPT5_FULL = "gpt-5.1"
GPT5_MINI = "gpt-5.1-mini"
GPT5_NANO = "gpt-5.1-nano"
GPT4O = "gpt-4o"


_LATEST_MODEL_ALIASES: tuple[tuple[str, str], ...] = (
    ("gpt-5-mini", GPT5_MINI),
    ("gpt-5-mini-latest", GPT5_MINI),
    ("gpt-5-nano", GPT5_NANO),
    ("gpt-5-nano-latest", GPT5_NANO),
    ("gpt-5", GPT5_FULL),
    ("gpt-5-latest", GPT5_FULL),
)

_LEGACY_MODEL_ALIASES: tuple[tuple[str, str], ...] = (
    ("gpt-4o-mini-2024-08-06", GPT5_NANO),
    ("gpt-4o-mini-2024-07-18", GPT5_NANO),
    ("gpt-4o-mini-2024-05-13", GPT5_NANO),
    ("gpt-4o-mini", GPT5_NANO),
    ("gpt-4o-latest", GPT5_MINI),
    ("gpt-4o-2024-08-06", GPT5_MINI),
    ("gpt-4o-2024-05-13", GPT5_MINI),
    ("gpt-4o", GPT5_MINI),
)


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

    for alias, replacement in _LATEST_MODEL_ALIASES:
        if lowered == alias or lowered.startswith(f"{alias}-"):
            return replacement

    for legacy, replacement in _LEGACY_MODEL_ALIASES:
        if lowered == legacy or lowered.startswith(f"{legacy}-"):
            return replacement

    if lowered.startswith("gpt-5.1-nano"):
        return GPT5_NANO
    if lowered.startswith("gpt-5.1-mini"):
        return GPT5_MINI
    if lowered.startswith("gpt-5.1"):
        return GPT5_FULL
    if lowered.startswith("gpt-5-nano"):
        return GPT5_NANO
    if lowered.startswith("gpt-5-mini"):
        return GPT5_MINI
    if lowered.startswith("gpt-5"):
        return GPT5_FULL
    if lowered.startswith("gpt-4o-mini"):
        return GPT5_NANO
    if lowered.startswith("gpt-4o"):
        return GPT4O
    return candidate


STREAMLIT_ENV = os.getenv("STREAMLIT_ENV", "development")
DEFAULT_LANGUAGE = os.getenv("LANGUAGE", "en")


def _canonical_model_name(value: str | None) -> str:
    """Return a lower-cased identifier suitable for availability tracking."""

    if not value:
        return ""
    return value.strip().lower()


def _detect_default_model() -> str:
    """Determine the default model for generic chat workloads."""

    env_default = os.getenv("DEFAULT_MODEL")
    if env_default:
        normalised = normalise_model_name(env_default)
        return normalised or GPT5_MINI
    return GPT5_MINI


DEFAULT_MODEL = _detect_default_model()
REASONING_LEVELS = ("minimal", "low", "medium", "high")
VERBOSITY_LEVELS = ("low", "medium", "high")


def _normalise_reasoning_effort(value: str | None, *, default: str = "medium") -> str:
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


REASONING_EFFORT = _normalise_reasoning_effort(os.getenv("REASONING_EFFORT", "medium"))


def normalise_verbosity(value: object | None, *, default: str = "medium") -> str:
    """Return a supported verbosity level or ``default`` when invalid."""

    if not isinstance(value, str):
        return default
    candidate = value.strip().lower()
    if not candidate:
        return default
    if candidate in VERBOSITY_LEVELS:
        return candidate
    warnings.warn(
        "Unsupported VERBOSITY '%s'; falling back to '%s'." % (candidate, default),
        RuntimeWarning,
    )
    return default


VERBOSITY = normalise_verbosity(os.getenv("VERBOSITY", "medium"))


def _normalise_timeout(value: object | None, *, default: float = 120.0) -> float:
    """Return a positive timeout value in seconds."""

    if value is None:
        return default
    candidate = value
    if isinstance(candidate, str):
        stripped = candidate.strip()
        if not stripped:
            return default
        try:
            candidate = float(stripped)
        except ValueError:
            warnings.warn(
                "Unsupported OPENAI_REQUEST_TIMEOUT '%s'; falling back to %.1f seconds." % (candidate, default),
                RuntimeWarning,
            )
            return default
    if isinstance(candidate, (int, float)):
        timeout = float(candidate)
        if timeout > 0:
            return timeout
    warnings.warn(
        "OPENAI_REQUEST_TIMEOUT must be a positive number; falling back to %.1f seconds." % default,
        RuntimeWarning,
    )
    return default


def _normalise_bool(value: object | None, *, default: bool = False) -> bool:
    """Return ``value`` converted to ``bool`` where possible."""

    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        candidate = value.strip().lower()
        if not candidate:
            return default
        if candidate in {"1", "true", "yes", "y", "on"}:
            return True
        if candidate in {"0", "false", "no", "n", "off"}:
            return False
    warnings.warn(
        "Unsupported boolean value %r; falling back to %s." % (value, default),
        RuntimeWarning,
    )
    return default


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = normalise_model_name(os.getenv("OPENAI_MODEL", DEFAULT_MODEL)) or DEFAULT_MODEL
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "").strip()
OPENAI_REQUEST_TIMEOUT = _normalise_timeout(os.getenv("OPENAI_REQUEST_TIMEOUT"), default=120.0)
USE_CLASSIC_API = _normalise_bool(os.getenv("USE_CLASSIC_API"), default=False)
VECTOR_STORE_ID = os.getenv("VECTOR_STORE_ID", "").strip()

try:
    openai_secrets = st.secrets["openai"]
    OPENAI_API_KEY = openai_secrets.get("OPENAI_API_KEY", OPENAI_API_KEY)
    OPENAI_MODEL = normalise_model_name(openai_secrets.get("OPENAI_MODEL", OPENAI_MODEL)) or OPENAI_MODEL
    OPENAI_BASE_URL = openai_secrets.get("OPENAI_BASE_URL", OPENAI_BASE_URL)
    timeout_secret = openai_secrets.get("OPENAI_REQUEST_TIMEOUT", OPENAI_REQUEST_TIMEOUT)
    OPENAI_REQUEST_TIMEOUT = _normalise_timeout(timeout_secret, default=OPENAI_REQUEST_TIMEOUT)
    if "USE_CLASSIC_API" in openai_secrets:
        USE_CLASSIC_API = _normalise_bool(openai_secrets.get("USE_CLASSIC_API"), default=USE_CLASSIC_API)
    VECTOR_STORE_ID = openai_secrets.get("VECTOR_STORE_ID", VECTOR_STORE_ID)
    VERBOSITY = normalise_verbosity(openai_secrets.get("VERBOSITY", VERBOSITY), default=VERBOSITY)
except Exception:
    openai_secrets = None

try:
    OPENAI_REQUEST_TIMEOUT = _normalise_timeout(
        st.secrets.get("OPENAI_REQUEST_TIMEOUT", OPENAI_REQUEST_TIMEOUT),
        default=OPENAI_REQUEST_TIMEOUT,
    )
    if "USE_CLASSIC_API" in st.secrets:
        USE_CLASSIC_API = _normalise_bool(st.secrets.get("USE_CLASSIC_API"), default=USE_CLASSIC_API)
except Exception:
    pass

try:
    REASONING_EFFORT = _normalise_reasoning_effort(
        st.secrets.get("REASONING_EFFORT", REASONING_EFFORT),
        default=REASONING_EFFORT,
    )
except Exception:
    pass

try:
    VERBOSITY = normalise_verbosity(st.secrets.get("VERBOSITY", VERBOSITY), default=VERBOSITY)
except Exception:
    pass


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


MODEL_ROUTING: Dict[str, str] = {
    ModelTask.DEFAULT.value: OPENAI_MODEL,
    ModelTask.EXTRACTION.value: GPT5_MINI,
    ModelTask.COMPANY_INFO.value: GPT5_MINI,
    ModelTask.FOLLOW_UP_QUESTIONS.value: GPT5_NANO,
    ModelTask.RAG_SUGGESTIONS.value: GPT5_NANO,
    ModelTask.SKILL_SUGGESTION.value: GPT5_NANO,
    ModelTask.BENEFIT_SUGGESTION.value: GPT5_NANO,
    ModelTask.TASK_SUGGESTION.value: GPT5_NANO,
    ModelTask.ONBOARDING_SUGGESTION.value: GPT5_NANO,
    ModelTask.JOB_AD.value: GPT5_MINI,
    ModelTask.INTERVIEW_GUIDE.value: GPT5_MINI,
    ModelTask.PROFILE_SUMMARY.value: GPT5_NANO,
    ModelTask.CANDIDATE_MATCHING.value: GPT5_MINI,
    ModelTask.DOCUMENT_REFINEMENT.value: GPT5_MINI,
    ModelTask.EXPLANATION.value: GPT5_MINI,
    "embedding": EMBED_MODEL,
}

for key, value in list(MODEL_ROUTING.items()):
    if key == "embedding":
        continue
    MODEL_ROUTING[key] = normalise_model_name(value) or value


MODEL_FALLBACKS: Dict[str, list[str]] = {
    _canonical_model_name(GPT5_FULL): [GPT5_FULL, GPT5_MINI, GPT4O, "gpt-3.5-turbo"],
    _canonical_model_name(GPT5_MINI): [GPT5_MINI, GPT4O, "gpt-3.5-turbo"],
    _canonical_model_name(GPT5_NANO): [GPT5_NANO, GPT4O, "gpt-3.5-turbo"],
    _canonical_model_name(GPT4O): [GPT4O, "gpt-3.5-turbo"],
    _canonical_model_name("gpt-3.5-turbo"): ["gpt-3.5-turbo"],
}


def _build_task_fallbacks() -> Dict[str, list[str]]:
    """Return fallback chains per task derived from :data:`MODEL_ROUTING`."""

    mapping: Dict[str, list[str]] = {}
    for task, model_name in MODEL_ROUTING.items():
        if task == "embedding":
            mapping[task] = [model_name]
            continue
        preferred = model_name or GPT5_MINI
        canonical = _canonical_model_name(preferred)
        fallbacks = MODEL_FALLBACKS.get(canonical, [preferred])
        # Ensure the preferred model is first in the list and remove duplicates while preserving order.
        options: list[str] = []
        for candidate in [preferred, *fallbacks]:
            if candidate and candidate not in options:
                options.append(candidate)
        mapping[task] = options
    return mapping


TASK_MODEL_FALLBACKS: Dict[str, list[str]] = _build_task_fallbacks()


_UNAVAILABLE_MODELS: set[str] = set()


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


def get_model_fallbacks_for(task: ModelTask | str) -> list[str]:
    """Return the fallback chain configured for ``task`` without overrides."""

    key = task.value if isinstance(task, ModelTask) else str(task)
    fallback_chain = TASK_MODEL_FALLBACKS.get(key)
    if fallback_chain is not None:
        return list(fallback_chain)
    return list(TASK_MODEL_FALLBACKS.get(ModelTask.DEFAULT.value, [GPT5_MINI, "gpt-3.5-turbo"]))


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


def _user_model_override() -> str | None:
    """Return a manually selected model override, if present."""

    try:
        raw_value = st.session_state.get("model_override")
        override = normalise_model_override(raw_value)
    except Exception:  # pragma: no cover - Streamlit session not initialised
        override = None
    if override:
        if raw_value != override:
            st.session_state["model_override"] = override
        return override
    return None


try:  # pragma: no cover - safe defaults when Streamlit session exists
    if "model" not in st.session_state:
        st.session_state["model"] = OPENAI_MODEL
    if "model_override" not in st.session_state:
        st.session_state["model_override"] = ""
except Exception:
    pass


def get_model_for(task: ModelTask | str, *, override: str | None = None) -> str:
    """Return the configured model for ``task`` respecting manual overrides."""

    return get_first_available_model(task, override=override)


def _collect_candidate_models(task: ModelTask | str, override: str | None) -> list[str]:
    """Assemble model candidates for ``task`` including manual overrides."""

    candidates: list[str] = []

    def _extend_with_model_chain(model_name: str) -> None:
        canonical = _canonical_model_name(model_name)
        if not canonical:
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
    user_override = _user_model_override()
    if user_override:
        override_name = normalise_model_name(user_override, prefer_latest=False) or user_override
        if override_name and override_name not in candidates:
            candidates.append(override_name)
            _extend_with_model_chain(override_name)
    for candidate in get_model_fallbacks_for(task):
        if candidate and candidate not in candidates:
            candidates.append(candidate)
    return candidates


def get_model_candidates(task: ModelTask | str, *, override: str | None = None) -> list[str]:
    """Return ordered model candidates for ``task`` including overrides."""

    return _collect_candidate_models(task, override)


def get_first_available_model(task: ModelTask | str, *, override: str | None = None) -> str:
    """Return the first available model for ``task`` using the configured fallbacks."""

    candidates = _collect_candidate_models(task, override)
    for index, candidate in enumerate(candidates):
        if is_model_available(candidate):
            if index > 0:
                logging.getLogger("cognitive_needs.model_routing").warning(
                    "Model '%s' unavailable; using fallback '%s'.", candidates[0], candidate
                )
            return candidate
    if candidates:
        logging.getLogger("cognitive_needs.model_routing").warning(
            "All configured models unavailable for task '%s'; using last candidate '%s'.",
            task,
            candidates[-1],
        )
        return candidates[-1]
    logging.getLogger("cognitive_needs.model_routing").error(
        "No model candidates resolved for task '%s'; falling back to %s.", task, GPT5_MINI
    )
    return GPT5_MINI


def get_active_verbosity() -> str:
    """Return the current verbosity level with session overrides."""

    try:
        value = st.session_state.get("verbosity")
    except Exception:  # pragma: no cover - Streamlit session not initialised
        value = None
    return normalise_verbosity(value, default=VERBOSITY)


if OPENAI_API_KEY:
    try:
        import openai

        openai.api_key = OPENAI_API_KEY
        if OPENAI_BASE_URL:
            openai.base_url = OPENAI_BASE_URL
    except ImportError:
        pass
else:
    warnings.warn(
        "OpenAI API key is not set. Set the OPENAI_API_KEY environment variable or add it to Streamlit secrets.",
        RuntimeWarning,
    )

SECRET_KEY = os.getenv("SECRET_KEY", "replace-me")
# (Moved UIKeys and DataKeys to constants/keys.py; import if needed)
