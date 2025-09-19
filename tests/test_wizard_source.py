import json

import pytest
import streamlit as st

from constants.keys import StateKeys, UIKeys
from models.need_analysis import NeedAnalysisProfile
from ingest.types import ContentBlock, StructuredDocument
from wizard import (
    on_file_uploaded,
    on_url_changed,
    _maybe_run_extraction,
    _step_onboarding,
    _extract_and_summarize,
)


class DummyContext:
    """Simple context manager used to stub column layouts."""

    def __enter__(self):
        return None

    def __exit__(self, exc_type, exc, tb) -> None:  # pragma: no cover - interface only
        return None


def _patch_onboarding_streamlit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch Streamlit calls used inside :func:`_step_onboarding`."""

    def fake_radio(label, options, *, key, **kwargs):
        if key == UIKeys.LANG_SELECT:
            # keep current language default
            st.session_state[key] = st.session_state.get(key, options[0])
            return st.session_state[key]
        if key == UIKeys.INPUT_METHOD:
            return st.session_state.get(UIKeys.INPUT_METHOD, options[0])
        return options[0]

    def fake_columns(spec, *_, **__):
        if isinstance(spec, int):
            count = spec
        elif isinstance(spec, (list, tuple)):
            count = len(spec)
        else:
            count = 2
        return tuple(DummyContext() for _ in range(count))

    def fake_tabs(labels):
        return [DummyContext() for _ in labels]

    monkeypatch.setattr(st, "radio", fake_radio)
    monkeypatch.setattr(st, "markdown", lambda *a, **k: None)
    monkeypatch.setattr(st, "subheader", lambda *a, **k: None)
    monkeypatch.setattr(st, "divider", lambda *a, **k: None)
    monkeypatch.setattr(st, "columns", fake_columns)
    monkeypatch.setattr(st, "info", lambda *a, **k: None)
    monkeypatch.setattr(st, "file_uploader", lambda *a, **k: None)
    monkeypatch.setattr(st, "caption", lambda *a, **k: None)
    monkeypatch.setattr(st, "tabs", fake_tabs)
    monkeypatch.setattr(st, "button", lambda *a, **k: False)
    monkeypatch.setattr(st, "rerun", lambda: None)


def test_on_file_uploaded_populates_state(monkeypatch: pytest.MonkeyPatch) -> None:
    """Uploading a file should queue extraction with the parsed text."""

    st.session_state.clear()
    st.session_state.lang = "en"
    st.session_state[UIKeys.PROFILE_FILE_UPLOADER] = object()
    monkeypatch.setattr(
        "wizard.extract_text_from_file",
        lambda _f: StructuredDocument(
            text="file text",
            blocks=[ContentBlock(type="paragraph", text="file text")],
        ),
    )

    on_file_uploaded()

    assert st.session_state["__prefill_profile_text__"] == "file text"
    assert st.session_state["__prefill_profile_doc__"].text == "file text"
    assert st.session_state[StateKeys.RAW_BLOCKS][0].text == "file text"
    assert st.session_state["__run_extraction__"] is True


def test_on_url_changed_populates_state(monkeypatch: pytest.MonkeyPatch) -> None:
    """Entering a URL should queue extraction with the downloaded text."""

    st.session_state.clear()
    st.session_state.lang = "en"
    st.session_state[UIKeys.PROFILE_URL_INPUT] = "https://example.com"
    monkeypatch.setattr(
        "wizard.extract_text_from_url",
        lambda _u: StructuredDocument(
            text="url text",
            blocks=[ContentBlock(type="paragraph", text="url text")],
        ),
    )

    on_url_changed()

    assert st.session_state["__prefill_profile_text__"] == "url text"
    assert st.session_state["__prefill_profile_doc__"].text == "url text"
    assert st.session_state[StateKeys.RAW_BLOCKS][0].text == "url text"
    assert st.session_state["__run_extraction__"] is True


def test_onboarding_transfers_prefill_to_raw_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prefilled text is copied into the RAW_TEXT slot when onboarding runs."""

    st.session_state.clear()
    st.session_state.lang = "en"
    st.session_state[UIKeys.INPUT_METHOD] = "file"
    st.session_state["__prefill_profile_text__"] = "prefilled"
    st.session_state[StateKeys.RAW_TEXT] = ""
    _patch_onboarding_streamlit(monkeypatch)
    called = False

    def fake_maybe_run_extraction(schema: dict) -> None:
        nonlocal called
        called = st.session_state.pop("__run_extraction__", False)

    monkeypatch.setattr("wizard._maybe_run_extraction", fake_maybe_run_extraction)

    _step_onboarding({})

    assert st.session_state[StateKeys.RAW_TEXT] == "prefilled"
    assert called is False


def test_maybe_run_extraction_uses_prefill_before_raw_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Extraction uses prefilled text when RAW_TEXT is still empty."""

    st.session_state.clear()
    st.session_state.lang = "en"
    st.session_state.model = "gpt"
    st.session_state[StateKeys.RAW_TEXT] = ""
    st.session_state["__prefill_profile_text__"] = "prefilled"
    st.session_state["__run_extraction__"] = True

    captured: dict[str, str] = {}

    def fake_extract(text: str, schema: dict) -> None:
        captured["text"] = text

    monkeypatch.setattr("wizard._extract_and_summarize", fake_extract)
    monkeypatch.setattr("wizard._autodetect_lang", lambda _t: None)
    monkeypatch.setattr(st, "rerun", lambda: None)
    warnings: list[str] = []
    monkeypatch.setattr(
        st, "warning", lambda message, *a, **k: warnings.append(message)
    )

    _maybe_run_extraction({})

    assert captured["text"] == "prefilled"
    assert st.session_state[StateKeys.RAW_TEXT] == "prefilled"
    assert st.session_state[StateKeys.RAW_BLOCKS]
    assert st.session_state[StateKeys.RAW_BLOCKS][0].type == "paragraph"
    assert warnings == []


def test_onboarding_triggers_extraction(monkeypatch: pytest.MonkeyPatch) -> None:
    """When the extraction flag is set the onboarding step should invoke it."""

    st.session_state.clear()
    st.session_state.lang = "en"
    st.session_state[UIKeys.INPUT_METHOD] = "file"
    st.session_state["__prefill_profile_text__"] = "prefilled"
    st.session_state["__run_extraction__"] = True
    _patch_onboarding_streamlit(monkeypatch)
    invoked: list[str] = []

    def fake_maybe_run_extraction(schema: dict) -> None:
        invoked.append("called")
        st.session_state[StateKeys.PROFILE] = {"position": {"job_title": "Test"}}

    monkeypatch.setattr("wizard._maybe_run_extraction", fake_maybe_run_extraction)

    _step_onboarding({})

    assert invoked == ["called"]
    assert st.session_state[StateKeys.PROFILE]["position"]["job_title"] == "Test"


def test_extract_and_summarize_does_not_enrich_skills(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ESCO enrichment is disabled so extracted skills remain untouched."""

    st.session_state.clear()
    st.session_state.lang = "en"
    st.session_state.model = "gpt"
    profile = NeedAnalysisProfile().model_dump()
    st.session_state[StateKeys.PROFILE] = profile
    st.session_state[StateKeys.RAW_TEXT] = "Job text"

    sample_data = {
        "position": {"job_title": "Engineer"},
        "requirements": {"hard_skills_required": ["Python"]},
    }

    monkeypatch.setattr("wizard.extract_json", lambda *a, **k: json.dumps(sample_data))
    monkeypatch.setattr("wizard.coerce_and_fill", NeedAnalysisProfile.model_validate)
    monkeypatch.setattr("wizard.apply_basic_fallbacks", lambda p, _t: p)
    _extract_and_summarize("Job text", {})

    data = st.session_state[StateKeys.PROFILE]
    assert data["position"]["occupation_label"] == ""
    assert data["requirements"]["hard_skills_required"] == ["Python"]


def test_extract_and_summarize_records_rag_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RAG context should be stored in profile metadata with values."""

    st.session_state.clear()
    st.session_state.lang = "en"
    st.session_state.model = "gpt"
    st.session_state.vector_store_id = "vs42"

    monkeypatch.setattr(
        "wizard.extract_json",
        lambda *a, **k: json.dumps({"position": {"job_title": "Engineer"}}),
    )
    monkeypatch.setattr("wizard.coerce_and_fill", NeedAnalysisProfile.model_validate)
    monkeypatch.setattr("wizard.apply_basic_fallbacks", lambda p, _t: p)
    _extract_and_summarize("Job text", {})

    metadata = st.session_state[StateKeys.PROFILE_METADATA]
    rag_meta = metadata["rag"]
    assert rag_meta["vector_store_id"] == "vs42"
    assert rag_meta["fields"] == {}
    assert rag_meta["global_context"] == []
    assert rag_meta["answers"] == {}
