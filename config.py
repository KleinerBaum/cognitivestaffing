"""Central configuration for the Cognitive Needs Responses API client.

The application uses cost-optimized ``gpt-4o-mini``/``gpt-4o`` models on
endpoints that support them and falls back to the widely available
``gpt-3.5-turbo`` for the public OpenAI API. Set ``DEFAULT_MODEL`` or
``OPENAI_MODEL`` to override the choice and use ``REASONING_EFFORT`` (``low`` |
``medium`` | ``high``) to control how much reasoning the model performs by
default.
"""

import os
import warnings

import streamlit as st

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


EMBED_MODEL = "text-embedding-3-small"  # RAG
STRICT_JSON = True
CHUNK_TOKENS = 600
CHUNK_OVERLAP = 0.1

STREAMLIT_ENV = os.getenv("STREAMLIT_ENV", "development")
DEFAULT_LANGUAGE = os.getenv("LANGUAGE", "en")


def _detect_default_model() -> str:
    """Determine a sensible default model based on the endpoint.

    ``DEFAULT_MODEL`` takes precedence if provided. Otherwise, the function
    selects ``gpt-4o-mini`` for known custom endpoints (Azure, OpenRouter or
    other non-public gateways) and ``gpt-3.5-turbo`` for the standard OpenAI
    API.
    """

    env_default = os.getenv("DEFAULT_MODEL")
    if env_default:
        return env_default

    base_url = os.getenv("OPENAI_BASE_URL", "")
    normalized_url = base_url.strip().lower()
    if not normalized_url:
        return "gpt-3.5-turbo"

    if any(host in normalized_url for host in ("openrouter.ai", "azure")):
        return "gpt-4o-mini"
    if "api.openai.com" in normalized_url:
        return "gpt-3.5-turbo"
    return "gpt-4o-mini"


DEFAULT_MODEL = _detect_default_model()
REASONING_EFFORT = os.getenv("REASONING_EFFORT", "medium")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", DEFAULT_MODEL)
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "").strip()
VECTOR_STORE_ID = os.getenv("VECTOR_STORE_ID", "").strip()

try:
    openai_secrets = st.secrets["openai"]
    OPENAI_API_KEY = openai_secrets.get("OPENAI_API_KEY", OPENAI_API_KEY)
    OPENAI_MODEL = openai_secrets.get("OPENAI_MODEL", OPENAI_MODEL)
    OPENAI_BASE_URL = openai_secrets.get("OPENAI_BASE_URL", OPENAI_BASE_URL)
    VECTOR_STORE_ID = openai_secrets.get("VECTOR_STORE_ID", VECTOR_STORE_ID)
except Exception:
    openai_secrets = None

try:
    REASONING_EFFORT = st.secrets.get("REASONING_EFFORT", REASONING_EFFORT)
except Exception:
    pass

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
