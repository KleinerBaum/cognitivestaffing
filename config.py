"""Central configuration for the Cognitive Needs Responses API client.

The application favours the officially supported OpenAI Responses models and
keeps lightweight tasks on ``gpt-4.1-mini``/``gpt-4.1-nano`` while escalating
reasoning-heavy workloads to the "o" series (``o4-mini`` or ``o3`` variants).
Automatic fallbacks continue down the stack (``o4-mini`` → ``o3`` →
``gpt-4o-mini`` → ``gpt-4o`` → ``gpt-4`` → ``gpt-3.5-turbo``) so the platform
remains resilient when specific tiers experience downtime. Structured retrieval
continues to use ``text-embedding-3-large`` (3,072 dimensions) for
higher-fidelity RAG vectors.

Set ``DEFAULT_MODEL`` or ``OPENAI_MODEL`` to override the primary model and use
``REASONING_EFFORT`` (``minimal`` | ``low`` | ``medium`` | ``high``) to control
how much reasoning the model performs by default.
"""

import logging
import os
import warnings

import streamlit as st
from enum import StrEnum
from typing import Dict, Mapping

from llm.model_router import ALIASES as ROUTER_ALIASES

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


logger = logging.getLogger(__name__)


EMBED_MODEL = "text-embedding-3-large"  # RAG
STRICT_JSON = True
CHUNK_TOKENS = 600
CHUNK_OVERLAP = 0.1

_TRUTHY_ENV_VALUES: tuple[str, ...] = ("1", "true", "yes", "on")


# Canonical model identifiers as exposed by the OpenAI Responses API.
GPT4 = "gpt-4"
GPT4O = "gpt-4o"
GPT4O_MINI = "gpt-4o-mini"
GPT41_MINI = "gpt-4.1-mini"
GPT41_NANO = "gpt-4.1-nano"
O4_MINI = "o4-mini"
O3 = "o3"
O3_MINI = "o3-mini"
GPT35 = "gpt-3.5-turbo"


_LATEST_MODEL_ALIASES: tuple[tuple[str, str], ...] = (
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

_LEGACY_MODEL_ALIASES: tuple[tuple[str, str], ...] = (
    ("gpt-4o-mini-2024-08-06", GPT4O_MINI),
    ("gpt-4o-mini-2024-07-18", GPT4O_MINI),
    ("gpt-4o-mini-2024-05-13", GPT4O_MINI),
    ("gpt-4o-mini", GPT4O_MINI),
    ("gpt-4o-2024-08-06", GPT4O),
    ("gpt-4o-2024-05-13", GPT4O),
    ("gpt-4o", GPT4O),
)


def _is_truthy_flag(value: str | None) -> bool:
    """Return ``True`` when ``value`` matches a truthy environment token."""

    if value is None:
        return False
    return value.strip().lower() in _TRUTHY_ENV_VALUES


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

    for alias, replacement in ROUTER_ALIASES.items():
        lowered_alias = alias.lower()
        if lowered == lowered_alias or lowered.startswith(f"{lowered_alias}-"):
            return replacement

    if lowered.startswith("gpt-4.1-mini"):
        return GPT41_MINI
    if lowered.startswith("gpt-4.1-nano"):
        return GPT41_NANO
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


STREAMLIT_ENV = os.getenv("STREAMLIT_ENV", "development")
DEFAULT_LANGUAGE = os.getenv("LANGUAGE", "en")

REASONING_LEVELS = ("minimal", "low", "medium", "high")


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

LIGHTWEIGHT_MODEL_DEFAULT = GPT41_MINI
REASONING_MODEL_DEFAULT = O4_MINI

_SUPPORTED_MODEL_CHOICES = {
    LIGHTWEIGHT_MODEL_DEFAULT,
    REASONING_MODEL_DEFAULT,
    GPT41_NANO,
    GPT41_MINI,
    O3,
    O3_MINI,
    GPT4O,
    GPT4O_MINI,
    GPT4,
    GPT35,
}


def _resolve_supported_model(value: str | None, fallback: str) -> str:
    """Normalise overrides to supported defaults with graceful degradation."""

    if not value:
        return fallback
    candidate = normalise_model_name(value)
    if candidate in _SUPPORTED_MODEL_CHOICES:
        return candidate
    if candidate:
        warnings.warn(
            "Unsupported default model '%s'; falling back to '%s'." % (candidate, fallback),
            RuntimeWarning,
        )
    return fallback


LIGHTWEIGHT_MODEL = _resolve_supported_model(
    os.getenv("LIGHTWEIGHT_MODEL"),
    LIGHTWEIGHT_MODEL_DEFAULT,
)
REASONING_MODEL = _resolve_supported_model(
    os.getenv("REASONING_MODEL"),
    REASONING_MODEL_DEFAULT,
)

_REASONING_MODEL_MAP: Dict[str, str] = {
    "minimal": LIGHTWEIGHT_MODEL,
    "low": LIGHTWEIGHT_MODEL,
    "medium": REASONING_MODEL,
    "high": REASONING_MODEL,
}


def _model_for_reasoning_level(level: str) -> str:
    """Return the preferred model for ``level`` of reasoning effort."""

    return _REASONING_MODEL_MAP.get(level, REASONING_MODEL)


def _canonical_model_name(value: str | None) -> str:
    """Return a lower-cased identifier suitable for availability tracking."""

    if not value:
        return ""
    return value.strip().lower()


def _detect_default_model() -> str:
    """Determine the default model for generic chat workloads."""

    env_default = os.getenv("DEFAULT_MODEL")
    if env_default:
        return _resolve_supported_model(env_default, _model_for_reasoning_level(REASONING_EFFORT))
    return _model_for_reasoning_level(REASONING_EFFORT)


DEFAULT_MODEL = _detect_default_model()
VERBOSITY_LEVELS = ("low", "medium", "high")


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


_missing_api_key_logged = False


def _coerce_secret_value(value: object) -> str:
    """Return ``value`` as a trimmed string without raising on unexpected types."""

    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (bytes, bytearray)):
        try:
            return value.decode("utf-8").strip()
        except Exception:  # pragma: no cover - defensive branch for binary blobs
            return ""
    return str(value).strip()


def get_openai_api_key() -> str:
    """Return the configured OpenAI API key from secrets or environment variables."""

    global _missing_api_key_logged

    # 1. Streamlit secrets (top-level key)
    try:
        direct_secret = st.secrets["OPENAI_API_KEY"]
    except Exception:
        direct_secret = None
    key = _coerce_secret_value(direct_secret)
    if key:
        _missing_api_key_logged = False
        return key

    # 2. Streamlit secrets (``openai`` section)
    try:
        openai_section = st.secrets["openai"]
    except Exception:
        openai_section = None
    if isinstance(openai_section, Mapping):
        section_key = _coerce_secret_value(openai_section.get("OPENAI_API_KEY"))
        if section_key:
            _missing_api_key_logged = False
            return section_key

    # 3. Environment variable fallback
    env_key = _coerce_secret_value(os.getenv("OPENAI_API_KEY"))
    if env_key:
        _missing_api_key_logged = False
        return env_key

    if not _missing_api_key_logged:
        logger.info(
            "OPENAI_API_KEY not configured; LLM-powered features are disabled until a key is provided.",
        )
        _missing_api_key_logged = True

    return ""


OPENAI_API_KEY = get_openai_api_key()
OPENAI_MODEL = _resolve_supported_model(os.getenv("OPENAI_MODEL"), DEFAULT_MODEL)
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "").strip()
OPENAI_ORGANIZATION = os.getenv("OPENAI_ORGANIZATION", "").strip()
OPENAI_PROJECT = os.getenv("OPENAI_PROJECT", "").strip()
OPENAI_REQUEST_TIMEOUT = _normalise_timeout(os.getenv("OPENAI_REQUEST_TIMEOUT"), default=120.0)
USE_CLASSIC_API = _normalise_bool(os.getenv("USE_CLASSIC_API"), default=False)
USE_RESPONSES_API = _normalise_bool(
    os.getenv("USE_RESPONSES_API"),
    default=not USE_CLASSIC_API,
)
# NO_TOOLS_IN_RESPONSES: Responses v2025 disables tool payloads by default.
RESPONSES_ALLOW_TOOLS = _normalise_bool(
    os.getenv("RESPONSES_ALLOW_TOOLS"),
    default=False,
)
VECTOR_STORE_ID = os.getenv("VECTOR_STORE_ID", "").strip()

try:
    openai_secrets = st.secrets["openai"]
    if isinstance(openai_secrets, Mapping):
        section_key = _coerce_secret_value(openai_secrets.get("OPENAI_API_KEY"))
        if section_key:
            OPENAI_API_KEY = section_key
        OPENAI_MODEL = _resolve_supported_model(openai_secrets.get("OPENAI_MODEL"), OPENAI_MODEL)
        OPENAI_BASE_URL = openai_secrets.get("OPENAI_BASE_URL", OPENAI_BASE_URL)
        OPENAI_ORGANIZATION = openai_secrets.get("OPENAI_ORGANIZATION", OPENAI_ORGANIZATION)
        OPENAI_PROJECT = openai_secrets.get("OPENAI_PROJECT", OPENAI_PROJECT)
        timeout_secret = openai_secrets.get("OPENAI_REQUEST_TIMEOUT", OPENAI_REQUEST_TIMEOUT)
        OPENAI_REQUEST_TIMEOUT = _normalise_timeout(timeout_secret, default=OPENAI_REQUEST_TIMEOUT)
        if "USE_CLASSIC_API" in openai_secrets:
            USE_CLASSIC_API = _normalise_bool(openai_secrets.get("USE_CLASSIC_API"), default=USE_CLASSIC_API)
        if "USE_RESPONSES_API" in openai_secrets:
            USE_RESPONSES_API = _normalise_bool(
                openai_secrets.get("USE_RESPONSES_API"),
                default=USE_RESPONSES_API,
            )
        if "RESPONSES_ALLOW_TOOLS" in openai_secrets:
            RESPONSES_ALLOW_TOOLS = _normalise_bool(
                openai_secrets.get("RESPONSES_ALLOW_TOOLS"),
                default=RESPONSES_ALLOW_TOOLS,
            )
        VECTOR_STORE_ID = openai_secrets.get("VECTOR_STORE_ID", VECTOR_STORE_ID)
        VERBOSITY = normalise_verbosity(openai_secrets.get("VERBOSITY", VERBOSITY), default=VERBOSITY)
    else:
        openai_secrets = None
except Exception:
    openai_secrets = None

try:
    OPENAI_ORGANIZATION = st.secrets.get("OPENAI_ORGANIZATION", OPENAI_ORGANIZATION)
    OPENAI_PROJECT = st.secrets.get("OPENAI_PROJECT", OPENAI_PROJECT)
except Exception:
    pass

try:
    OPENAI_REQUEST_TIMEOUT = _normalise_timeout(
        st.secrets.get("OPENAI_REQUEST_TIMEOUT", OPENAI_REQUEST_TIMEOUT),
        default=OPENAI_REQUEST_TIMEOUT,
    )
    if "USE_CLASSIC_API" in st.secrets:
        USE_CLASSIC_API = _normalise_bool(st.secrets.get("USE_CLASSIC_API"), default=USE_CLASSIC_API)
    if "USE_RESPONSES_API" in st.secrets:
        USE_RESPONSES_API = _normalise_bool(
            st.secrets.get("USE_RESPONSES_API"),
            default=USE_RESPONSES_API,
        )
    if "RESPONSES_ALLOW_TOOLS" in st.secrets:
        RESPONSES_ALLOW_TOOLS = _normalise_bool(
            st.secrets.get("RESPONSES_ALLOW_TOOLS"),
            default=RESPONSES_ALLOW_TOOLS,
        )
except Exception:
    pass

LLM_ENABLED = bool(OPENAI_API_KEY)

if USE_RESPONSES_API:
    USE_CLASSIC_API = False
else:
    USE_CLASSIC_API = True

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


def is_llm_enabled() -> bool:
    """Return ``True`` when an OpenAI API key is configured."""

    return bool(OPENAI_API_KEY)


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


def _load_model_routing_overrides() -> Dict[str, str]:
    """Return MODEL_ROUTING overrides sourced from env vars or secrets."""

    overrides: Dict[str, str] = {}
    prefix = "MODEL_ROUTING__"
    for env_key, env_value in os.environ.items():
        if not env_key.startswith(prefix):
            continue
        raw_key = env_key[len(prefix) :].strip().lower()
        if not raw_key:
            continue
        value = _coerce_secret_value(env_value)
        if value:
            overrides[raw_key] = value

    try:
        secrets_overrides = st.secrets.get("MODEL_ROUTING")
    except Exception:
        secrets_overrides = None
    if isinstance(secrets_overrides, Mapping):
        for raw_key, raw_value in secrets_overrides.items():
            if not isinstance(raw_key, str):
                continue
            normalised_key = raw_key.strip().lower()
            if not normalised_key:
                continue
            value = _coerce_secret_value(raw_value)
            if value:
                overrides[normalised_key] = value

    return overrides


MODEL_ROUTING: Dict[str, str] = {
    ModelTask.DEFAULT.value: OPENAI_MODEL,
    ModelTask.EXTRACTION.value: LIGHTWEIGHT_MODEL,
    ModelTask.COMPANY_INFO.value: LIGHTWEIGHT_MODEL,
    ModelTask.FOLLOW_UP_QUESTIONS.value: REASONING_MODEL,
    ModelTask.RAG_SUGGESTIONS.value: REASONING_MODEL,
    ModelTask.SKILL_SUGGESTION.value: REASONING_MODEL,
    ModelTask.BENEFIT_SUGGESTION.value: REASONING_MODEL,
    ModelTask.TASK_SUGGESTION.value: REASONING_MODEL,
    ModelTask.ONBOARDING_SUGGESTION.value: REASONING_MODEL,
    ModelTask.JOB_AD.value: REASONING_MODEL,
    ModelTask.INTERVIEW_GUIDE.value: REASONING_MODEL,
    ModelTask.PROFILE_SUMMARY.value: REASONING_MODEL,
    ModelTask.CANDIDATE_MATCHING.value: REASONING_MODEL,
    ModelTask.DOCUMENT_REFINEMENT.value: REASONING_MODEL,
    ModelTask.EXPLANATION.value: REASONING_MODEL,
    ModelTask.SALARY_ESTIMATE.value: REASONING_MODEL,
    ModelTask.JSON_REPAIR.value: LIGHTWEIGHT_MODEL,
    "embedding": EMBED_MODEL,
}

# MODEL_ROUTING_NANO: lightweight vs reasoning shortcuts for generic callers.
MODEL_ROUTING.update(
    {
        "non_reasoning": LIGHTWEIGHT_MODEL,
        "reasoning": REASONING_MODEL,
    }
)

_MODEL_ROUTING_OVERRIDES = _load_model_routing_overrides()
if _MODEL_ROUTING_OVERRIDES:
    default_fallback = MODEL_ROUTING.get(ModelTask.DEFAULT.value, DEFAULT_MODEL) or DEFAULT_MODEL
    for override_key, override_value in _MODEL_ROUTING_OVERRIDES.items():
        if override_key == "embedding":
            MODEL_ROUTING[override_key] = override_value
            continue
        fallback = MODEL_ROUTING.get(override_key, default_fallback) or default_fallback
        MODEL_ROUTING[override_key] = _resolve_supported_model(override_value, fallback)

for key, value in list(MODEL_ROUTING.items()):
    if key == "embedding":
        continue
    MODEL_ROUTING[key] = normalise_model_name(value) or value


MODEL_FALLBACKS: Dict[str, list[str]] = {
    _canonical_model_name(GPT41_MINI): [
        GPT41_MINI,
        GPT41_NANO,
        GPT4O_MINI,
        GPT4O,
        GPT4,
        GPT35,
    ],
    _canonical_model_name(GPT41_NANO): [
        GPT41_NANO,
        GPT4O_MINI,
        GPT4O,
        GPT4,
        GPT35,
    ],
    _canonical_model_name(O4_MINI): [
        O4_MINI,
        O3_MINI,
        O3,
        GPT4O,
        GPT4,
        GPT35,
    ],
    _canonical_model_name(O3_MINI): [
        O3_MINI,
        O3,
        O4_MINI,
        GPT4O,
        GPT4,
        GPT35,
    ],
    _canonical_model_name(O3): [
        O3,
        O4_MINI,
        GPT4O,
        GPT4,
        GPT35,
    ],
    _canonical_model_name(GPT4O_MINI): [
        GPT4O_MINI,
        GPT4O,
        GPT4,
        GPT35,
    ],
    _canonical_model_name(GPT4O): [
        GPT4O,
        GPT4,
        GPT35,
    ],
    _canonical_model_name(GPT4): [
        GPT4,
        GPT35,
    ],
    _canonical_model_name(GPT35): [
        GPT35,
    ],
}


def _build_task_fallbacks() -> Dict[str, list[str]]:
    """Return fallback chains per task derived from :data:`MODEL_ROUTING`."""

    mapping: Dict[str, list[str]] = {}
    for task, model_name in MODEL_ROUTING.items():
        if task == "embedding":
            mapping[task] = [model_name]
            continue
        preferred = model_name or OPENAI_MODEL or LIGHTWEIGHT_MODEL_DEFAULT
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
    return list(TASK_MODEL_FALLBACKS.get(ModelTask.DEFAULT.value, [GPT4O, "gpt-3.5-turbo"]))


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
    logger.error("No model candidates resolved for task '%s'; falling back to %s.", task, GPT4O)
    return GPT4O


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

SECRET_KEY = os.getenv("SECRET_KEY", "replace-me")
# (Moved UIKeys and DataKeys to constants/keys.py; import if needed)
