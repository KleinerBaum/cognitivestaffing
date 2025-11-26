from __future__ import annotations

import pytest
import streamlit as st

from openai_utils.errors import LLMTimeoutError
from wizard import flow


def test_timeout_warning_is_bilingual_and_friendly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(st, "session_state", {"lang": "en"})
    warning_en = flow._resolve_extraction_warning(LLMTimeoutError("timeout", timeout_seconds=60.0))
    assert "taking longer than usual" in warning_en

    st.session_state["lang"] = "de"
    warning_de = flow._resolve_extraction_warning(LLMTimeoutError("timeout", timeout_seconds=60.0))
    assert "länger als erwartet" in warning_de
