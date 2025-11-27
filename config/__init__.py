"""Central configuration for the Cognitive Needs Responses API client.

The application favours the officially supported OpenAI Responses models and
keeps lightweight tasks on ``gpt-4o-mini`` while escalating reasoning-heavy
workloads through ``o3`` depending on the configured
``REASONING_EFFORT``. Automatic fallbacks continue down the stack
(``o3`` → ``o4-mini`` → ``gpt-4o-mini`` → ``gpt-4o`` → ``gpt-4`` →
``gpt-3.5-turbo``) so the platform remains resilient when specific tiers
experience downtime. Structured retrieval continues to use
``text-embedding-3-large`` (3,072 dimensions) for higher-fidelity RAG vectors.

``REASONING_EFFORT`` (``minimal`` | ``low`` | ``medium`` | ``high``) controls
how much reasoning the model performs by default.
"""

import logging
import os
import warnings
from contextlib import contextmanager
from threading import RLock

import streamlit as st
from enum import StrEnum
from typing import Dict, Iterator, Mapping
from . import models as model_config

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


logger = logging.getLogger(__name__)


STRICT_JSON = True
CHUNK_TOKENS = 600
CHUNK_OVERLAP = 0.1

_TRUTHY_ENV_VALUES: tuple[str, ...] = ("1", "true", "yes", "on")
_API_FLAG_LOCK = RLock()

# Populated by ``_configure_models`` during import.
DEFAULT_MODEL: str
EMBED_MODEL: str
HIGH_REASONING_MODEL: str
LIGHTWEIGHT_MODEL: str
MEDIUM_REASONING_MODEL: str
MODEL_ROUTING: Dict[str, str]
OPENAI_MODEL: str
REASONING_MODEL: str
TASK_MODEL_FALLBACKS: Dict[str, list[str]]


class APIMode(StrEnum):
    """Enumerate the supported OpenAI API backends."""

    RESPONSES = "responses"
    CLASSIC = "chat"

    @property
    def is_classic(self) -> bool:
        return self is APIMode.CLASSIC


def _is_truthy_flag(value: str | None) -> bool:
    """Return ``True`` when ``value`` matches a truthy environment token."""

    if value is None:
        return False
    return value.strip().lower() in _TRUTHY_ENV_VALUES


def _parse_positive_int_env(value: object | None, *, env_var: str) -> int | None:
    """Return a positive integer parsed from ``value`` or ``None``."""

    if value is None:
        return None
    if isinstance(value, str):
        candidate = value.strip()
        if not candidate:
            return None
        try:
            parsed = int(float(candidate))
        except ValueError:
            warnings.warn(
                "%s is not a number; ignoring %s" % (candidate, env_var),
                RuntimeWarning,
            )
            return None
    elif isinstance(value, (int, float)):
        parsed = int(value)
    else:
        warnings.warn(
            "Unsupported %s value '%s'; ignoring budget guard." % (env_var, value),
            RuntimeWarning,
        )
        return None
    if parsed <= 0:
        return None
    return parsed


SCHEMA_FUNCTION_FALLBACK = _is_truthy_flag(os.getenv("SCHEMA_FUNCTION_FALLBACK"))
SCHEMA_FUNCTION_NAME = os.getenv("SCHEMA_FUNCTION_NAME", "extract_profile")
SCHEMA_FUNCTION_DESCRIPTION = os.getenv(
    "SCHEMA_FUNCTION_DESCRIPTION",
    "Extract the structured profile payload / Extrahiere die strukturierte Profilantwort.",
)


def _coerce_api_mode_value(value: APIMode | str | bool | None, *, fallback: APIMode) -> APIMode:
    """Convert ``value`` into an :class:`APIMode` with a sensible default."""

    if isinstance(value, APIMode):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {APIMode.RESPONSES.value, "response", "responses"}:
            return APIMode.RESPONSES
        if lowered in {APIMode.CLASSIC.value, "classic", "legacy", "chat"}:
            return APIMode.CLASSIC
    if isinstance(value, bool):
        return APIMode.RESPONSES if value else APIMode.CLASSIC
    return fallback


normalise_model_name = model_config.normalise_model_name
normalise_model_override = model_config.normalise_model_override


STREAMLIT_ENV = os.getenv("STREAMLIT_ENV", "development")
DEFAULT_LANGUAGE = os.getenv("LANGUAGE", "en")

_raw_budget_limit = os.getenv("OPENAI_SESSION_TOKEN_LIMIT") or os.getenv("OPENAI_TOKEN_BUDGET")
OPENAI_SESSION_TOKEN_LIMIT = _parse_positive_int_env(_raw_budget_limit, env_var="OPENAI_SESSION_TOKEN_LIMIT")

CHATKIT_ENABLED = _is_truthy_flag(os.getenv("CHATKIT_ENABLED", "1"))
CHATKIT_DOMAIN_KEY = os.getenv("CHATKIT_DOMAIN_KEY", "")
CHATKIT_WORKFLOW_ID = os.getenv("CHATKIT_WORKFLOW_ID", "")
CHATKIT_FOLLOWUPS_WORKFLOW_ID = os.getenv("CHATKIT_FOLLOWUPS_WORKFLOW_ID", CHATKIT_WORKFLOW_ID)
CHATKIT_RESPONSIBILITIES_WORKFLOW_ID = os.getenv("CHATKIT_RESPONSIBILITIES_WORKFLOW_ID", "")
CHATKIT_COMPANY_WORKFLOW_ID = os.getenv("CHATKIT_COMPANY_WORKFLOW_ID", "")
CHATKIT_TEAM_WORKFLOW_ID = os.getenv("CHATKIT_TEAM_WORKFLOW_ID", "")
CHATKIT_SKILLS_WORKFLOW_ID = os.getenv("CHATKIT_SKILLS_WORKFLOW_ID", "")
CHATKIT_COMPENSATION_WORKFLOW_ID = os.getenv("CHATKIT_COMPENSATION_WORKFLOW_ID", "")
CHATKIT_PROCESS_WORKFLOW_ID = os.getenv("CHATKIT_PROCESS_WORKFLOW_ID", "")

REASONING_LEVELS = model_config.REASONING_LEVELS
REASONING_EFFORT = model_config.normalise_reasoning_effort(os.getenv("REASONING_EFFORT", model_config.REASONING_EFFORT))
_lightweight_override = os.getenv("LIGHTWEIGHT_MODEL")
_medium_reasoning_override = os.getenv("MEDIUM_REASONING_MODEL")
_high_reasoning_override = os.getenv("REASONING_MODEL") or os.getenv("HIGH_REASONING_MODEL")


def _warn_deprecated_model_override(source: str, value: str | None) -> None:
    if not value:
        return
    logger.warning(
        "Ignoring %s model override '%s'; the primary model is fixed to '%s'.",
        source,
        value,
        model_config.PRIMARY_MODEL_DEFAULT,
    )


_default_model_override_env = os.getenv("DEFAULT_MODEL")
_openai_model_override_env = os.getenv("OPENAI_MODEL")
_warn_deprecated_model_override("DEFAULT_MODEL env", _default_model_override_env)
_warn_deprecated_model_override("OPENAI_MODEL env", _openai_model_override_env)

_default_model_override: str | None = None
_openai_model_override: str | None = None
_MODEL_ROUTING_OVERRIDES: Dict[str, str] = {}
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


def _configure_models() -> None:
    global DEFAULT_MODEL, EMBED_MODEL, HIGH_REASONING_MODEL, LIGHTWEIGHT_MODEL
    global MEDIUM_REASONING_MODEL, MODEL_ROUTING, OPENAI_MODEL, REASONING_EFFORT
    global REASONING_MODEL, TASK_MODEL_FALLBACKS

    model_config.configure_models(
        reasoning_effort=REASONING_EFFORT,
        lightweight_override=_lightweight_override,
        medium_reasoning_override=_medium_reasoning_override,
        high_reasoning_override=_high_reasoning_override,
        default_model_override=_default_model_override,
        openai_model_override=_openai_model_override,
        model_routing_overrides=_MODEL_ROUTING_OVERRIDES,
    )
    REASONING_EFFORT = model_config.REASONING_EFFORT
    LIGHTWEIGHT_MODEL = model_config.LIGHTWEIGHT_MODEL
    MEDIUM_REASONING_MODEL = model_config.MEDIUM_REASONING_MODEL
    HIGH_REASONING_MODEL = model_config.HIGH_REASONING_MODEL
    REASONING_MODEL = model_config.REASONING_MODEL
    DEFAULT_MODEL = model_config.DEFAULT_MODEL
    OPENAI_MODEL = model_config.OPENAI_MODEL
    MODEL_ROUTING = model_config.MODEL_ROUTING
    TASK_MODEL_FALLBACKS = model_config.TASK_MODEL_FALLBACKS
    EMBED_MODEL = model_config.EMBED_MODEL


_configure_models()


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
_OPENAI_BASE_URL_ENV = os.getenv("OPENAI_BASE_URL") or os.getenv("OPENAI_API_BASE_URL")
OPENAI_BASE_URL = (_OPENAI_BASE_URL_ENV or "").strip()
OPENAI_ORGANIZATION = os.getenv("OPENAI_ORGANIZATION", "").strip()
OPENAI_PROJECT = os.getenv("OPENAI_PROJECT", "").strip()
OPENAI_REQUEST_TIMEOUT = _normalise_timeout(os.getenv("OPENAI_REQUEST_TIMEOUT"), default=120.0)
# API mode flags are initialised via ``set_api_mode`` to guarantee synchronisation.
USE_CLASSIC_API = True
USE_RESPONSES_API = False

ADMIN_DEBUG_PANEL = _normalise_bool(
    os.getenv("ADMIN_DEBUG_PANEL"),
    default=False,
)


def resolve_api_mode(preferred: APIMode | str | bool | None = None) -> APIMode:
    """Return the active API mode, optionally honouring an override."""

    fallback = APIMode.CLASSIC if USE_CLASSIC_API else APIMode.RESPONSES
    return _coerce_api_mode_value(preferred, fallback=fallback)


def set_api_mode(mode: APIMode | str | bool) -> None:
    """Synchronise the Responses/Classic API flags.

    Args:
        mode: When truthy/``APIMode.RESPONSES`` the Responses API becomes the
            active backend. ``False`` or ``APIMode.CLASSIC`` switches the
            platform to the legacy Chat Completions API.
    """

    global USE_RESPONSES_API, USE_CLASSIC_API

    target_mode = _coerce_api_mode_value(mode, fallback=resolve_api_mode())
    USE_RESPONSES_API = target_mode is APIMode.RESPONSES
    USE_CLASSIC_API = target_mode is APIMode.CLASSIC


def _resolve_env_api_mode() -> APIMode:
    """Return the initial API mode derived from environment toggles.

    ``USE_RESPONSES_API`` takes precedence when both flags are provided to avoid
    accidental divergence. When neither variable is set, the Chat Completions
    API is the default.
    """

    responses_raw = os.getenv("USE_RESPONSES_API")
    classic_raw = os.getenv("USE_CLASSIC_API")

    if responses_raw is not None:
        responses_enabled = _normalise_bool(responses_raw, default=False)
        return APIMode.RESPONSES if responses_enabled else APIMode.CLASSIC

    if classic_raw is not None:
        classic_enabled = _normalise_bool(classic_raw, default=True)
        return APIMode.CLASSIC if classic_enabled else APIMode.RESPONSES

    return APIMode.CLASSIC


def set_responses_allow_tools(allow_tools: bool) -> None:
    """Synchronise the ``RESPONSES_ALLOW_TOOLS`` flag at runtime."""

    global RESPONSES_ALLOW_TOOLS

    RESPONSES_ALLOW_TOOLS = bool(allow_tools)


@contextmanager
def temporarily_force_classic_api() -> Iterator[None]:
    """Temporarily switch to the classic Chat API inside the managed block."""

    previous_mode = resolve_api_mode()
    try:
        set_api_mode(APIMode.CLASSIC)
        yield
    finally:
        set_api_mode(previous_mode)


set_api_mode(_resolve_env_api_mode())
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
        if "OPENAI_MODEL" in openai_secrets:
            _warn_deprecated_model_override(
                "OPENAI_MODEL secret",
                _coerce_secret_value(openai_secrets.get("OPENAI_MODEL")),
            )
        OPENAI_BASE_URL = openai_secrets.get("OPENAI_BASE_URL", OPENAI_BASE_URL)
        OPENAI_ORGANIZATION = openai_secrets.get("OPENAI_ORGANIZATION", OPENAI_ORGANIZATION)
        OPENAI_PROJECT = openai_secrets.get("OPENAI_PROJECT", OPENAI_PROJECT)
        timeout_secret = openai_secrets.get("OPENAI_REQUEST_TIMEOUT", OPENAI_REQUEST_TIMEOUT)
        OPENAI_REQUEST_TIMEOUT = _normalise_timeout(timeout_secret, default=OPENAI_REQUEST_TIMEOUT)
        if "USE_CLASSIC_API" in openai_secrets:
            set_api_mode(
                not _normalise_bool(
                    openai_secrets.get("USE_CLASSIC_API"),
                    default=USE_CLASSIC_API,
                )
            )
        if "USE_RESPONSES_API" in openai_secrets:
            set_api_mode(
                _normalise_bool(
                    openai_secrets.get("USE_RESPONSES_API"),
                    default=USE_RESPONSES_API,
                )
            )
        if "RESPONSES_ALLOW_TOOLS" in openai_secrets:
            set_responses_allow_tools(
                _normalise_bool(
                    openai_secrets.get("RESPONSES_ALLOW_TOOLS"),
                    default=RESPONSES_ALLOW_TOOLS,
                )
            )
        if "ADMIN_DEBUG_PANEL" in openai_secrets:
            ADMIN_DEBUG_PANEL = _normalise_bool(
                openai_secrets.get("ADMIN_DEBUG_PANEL"),
                default=ADMIN_DEBUG_PANEL,
            )
        VECTOR_STORE_ID = openai_secrets.get("VECTOR_STORE_ID", VECTOR_STORE_ID)
        VERBOSITY = normalise_verbosity(openai_secrets.get("VERBOSITY", VERBOSITY), default=VERBOSITY)
    else:
        openai_secrets = None
except Exception:
    openai_secrets = None

_configure_models()

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
        set_api_mode(
            not _normalise_bool(
                st.secrets.get("USE_CLASSIC_API"),
                default=USE_CLASSIC_API,
            )
        )
    if "USE_RESPONSES_API" in st.secrets:
        set_api_mode(
            _normalise_bool(
                st.secrets.get("USE_RESPONSES_API"),
                default=USE_RESPONSES_API,
            )
        )
    if "RESPONSES_ALLOW_TOOLS" in st.secrets:
        set_responses_allow_tools(
            _normalise_bool(
                st.secrets.get("RESPONSES_ALLOW_TOOLS"),
                default=RESPONSES_ALLOW_TOOLS,
            )
        )
    if "ADMIN_DEBUG_PANEL" in st.secrets:
        ADMIN_DEBUG_PANEL = _normalise_bool(
            st.secrets.get("ADMIN_DEBUG_PANEL"),
            default=ADMIN_DEBUG_PANEL,
        )
except Exception:
    pass

LLM_ENABLED = bool(OPENAI_API_KEY)


def is_llm_enabled() -> bool:
    """Return ``True`` when an OpenAI API key is configured."""

    return bool(OPENAI_API_KEY)


assert not (USE_RESPONSES_API and USE_CLASSIC_API), (
    "USE_RESPONSES_API and USE_CLASSIC_API cannot both be enabled simultaneously"
)

try:
    REASONING_EFFORT = model_config.normalise_reasoning_effort(
        st.secrets.get("REASONING_EFFORT", REASONING_EFFORT),
        default=REASONING_EFFORT,
    )
except Exception:
    pass

try:
    VERBOSITY = normalise_verbosity(st.secrets.get("VERBOSITY", VERBOSITY), default=VERBOSITY)
except Exception:
    pass


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


_MODEL_ROUTING_OVERRIDES = _load_model_routing_overrides()
_configure_models()

try:  # pragma: no cover - safe defaults when Streamlit session exists
    if "model" not in st.session_state:
        st.session_state["model"] = OPENAI_MODEL
except Exception:
    pass


def get_active_verbosity() -> str:
    """Return the current verbosity level with session overrides."""

    try:
        value = st.session_state.get("verbosity")
    except Exception:  # pragma: no cover - Streamlit session not initialised
        value = None
    return normalise_verbosity(value, default=VERBOSITY)


GPT4 = model_config.GPT4
GPT4O = model_config.GPT4O
GPT4O_MINI = model_config.GPT4O_MINI
GPT51 = model_config.GPT51
GPT51_MINI = model_config.GPT51_MINI
GPT51_NANO = model_config.GPT51_NANO
GPT41_MINI = model_config.GPT41_MINI
GPT41_NANO = model_config.GPT41_NANO
O4_MINI = model_config.O4_MINI
O3 = model_config.O3
O3_MINI = model_config.O3_MINI
GPT35 = model_config.GPT35

ModelTask = model_config.ModelTask
get_model_for = model_config.get_model_for
select_model = model_config.select_model
get_model_candidates = model_config.get_model_candidates
get_first_available_model = model_config.get_first_available_model
get_model_fallbacks_for = model_config.get_model_fallbacks_for
get_reasoning_mode = model_config.get_reasoning_mode
clear_unavailable_models = model_config.clear_unavailable_models
mark_model_unavailable = model_config.mark_model_unavailable
is_model_available = model_config.is_model_available


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
