"""Central configuration for the Cognitive Needs Responses API client.

The application now routes requests between OpenAI's GPT-5 family to balance
quality and cost. ``gpt-5-mini`` serves as the default large language model for
generative workloads, while ``gpt-5-nano`` powers lightweight suggestion flows.
Structured retrieval keeps using ``text-embedding-3-small``.

Set ``DEFAULT_MODEL`` or ``OPENAI_MODEL`` to override the primary model and use
``REASONING_EFFORT`` (``low`` | ``medium`` | ``high``) to control how much
reasoning the model performs by default.
"""

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


EMBED_MODEL = "text-embedding-3-small"  # RAG
STRICT_JSON = True
CHUNK_TOKENS = 600
CHUNK_OVERLAP = 0.1


def normalise_model_name(value: str | None) -> str:
    """Return ``value`` with legacy model aliases mapped to current names."""

    if not value:
        return ""
    candidate = value.strip()
    if not candidate:
        return ""

    lowered = candidate.lower()
    legacy_aliases = [
        ("gpt-4o-mini-2024-08-06", "gpt-5-nano"),
        ("gpt-4o-mini-2024-07-18", "gpt-5-nano"),
        ("gpt-4o-mini-2024-05-13", "gpt-5-nano"),
        ("gpt-4o-mini", "gpt-5-nano"),
        ("gpt-4o-latest", "gpt-5-mini"),
        ("gpt-4o-2024-08-06", "gpt-5-mini"),
        ("gpt-4o-2024-05-13", "gpt-5-mini"),
        ("gpt-4o", "gpt-5-mini"),
    ]

    for legacy, replacement in legacy_aliases:
        if lowered == legacy or lowered.startswith(f"{legacy}-"):
            return replacement

    if lowered.startswith("gpt-4o-mini"):
        return "gpt-5-nano"
    if lowered.startswith("gpt-4o"):
        return "gpt-5-mini"
    return candidate


STREAMLIT_ENV = os.getenv("STREAMLIT_ENV", "development")
DEFAULT_LANGUAGE = os.getenv("LANGUAGE", "en")


def _detect_default_model() -> str:
    """Determine the default model for generic chat workloads."""

    env_default = os.getenv("DEFAULT_MODEL")
    if env_default:
        normalised = normalise_model_name(env_default)
        return normalised or "gpt-5-mini"
    return "gpt-5-mini"


DEFAULT_MODEL = _detect_default_model()
REASONING_EFFORT = os.getenv("REASONING_EFFORT", "medium")


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = normalise_model_name(os.getenv("OPENAI_MODEL", DEFAULT_MODEL)) or DEFAULT_MODEL
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "").strip()
VECTOR_STORE_ID = os.getenv("VECTOR_STORE_ID", "").strip()

try:
    openai_secrets = st.secrets["openai"]
    OPENAI_API_KEY = openai_secrets.get("OPENAI_API_KEY", OPENAI_API_KEY)
    OPENAI_MODEL = normalise_model_name(openai_secrets.get("OPENAI_MODEL", OPENAI_MODEL)) or OPENAI_MODEL
    OPENAI_BASE_URL = openai_secrets.get("OPENAI_BASE_URL", OPENAI_BASE_URL)
    VECTOR_STORE_ID = openai_secrets.get("VECTOR_STORE_ID", VECTOR_STORE_ID)
except Exception:
    openai_secrets = None

try:
    REASONING_EFFORT = st.secrets.get("REASONING_EFFORT", REASONING_EFFORT)
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


GPT5_MINI = "gpt-5-mini"
GPT5_NANO = "gpt-5-nano"


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

    if override:
        return normalise_model_name(override) or GPT5_MINI
    user_override = _user_model_override()
    if user_override:
        return user_override
    key = task.value if isinstance(task, ModelTask) else str(task)
    return MODEL_ROUTING.get(key, GPT5_MINI)


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
