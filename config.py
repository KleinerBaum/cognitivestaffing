import os
import warnings

import streamlit as st

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


EMBED_MODEL = "text-embedding-3-small" # RAG
STRICT_JSON = True
CHUNK_TOKENS = 600
CHUNK_OVERLAP = 0.1

STREAMLIT_ENV = os.getenv("STREAMLIT_ENV", "development")
DEFAULT_LANGUAGE = os.getenv("LANGUAGE", "en")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gpt-3.5-turbo")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", DEFAULT_MODEL)
VECTOR_STORE_ID = os.getenv("VECTOR_STORE_ID", "").strip()

try:
    openai_secrets = st.secrets["openai"]
    OPENAI_API_KEY = openai_secrets.get("OPENAI_API_KEY", OPENAI_API_KEY)
    OPENAI_MODEL = openai_secrets.get("OPENAI_MODEL", OPENAI_MODEL)
    VECTOR_STORE_ID = openai_secrets.get("VECTOR_STORE_ID", VECTOR_STORE_ID)
except Exception:
    openai_secrets = None

if OPENAI_API_KEY:
    try:
        import openai

        openai.api_key = OPENAI_API_KEY
    except ImportError:
        pass
else:
    warnings.warn(
        "OpenAI API key is not set. Set the OPENAI_API_KEY environment variable or add it to Streamlit secrets.",
        RuntimeWarning,
    )

SECRET_KEY = os.getenv("SECRET_KEY", "replace-me")


class UIKeys:
    """Session keys for UI widgets."""

    JD_TEXT_INPUT = "ui.jd_text_input"
    JD_FILE_UPLOADER = "ui.jd_file_uploader"
    JD_URL_INPUT = "ui.jd_url_input"


class DataKeys:
    """Session keys for business data."""

    JD_TEXT = "data.jd_text"
    PROFILE = "data.profile"
    STEP = "data.step"
