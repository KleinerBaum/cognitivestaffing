import json
import sys
from pathlib import Path
from typing import Any, Mapping

import pytest
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import question_logic

from constants.keys import StateKeys, UIKeys
from core.confidence import ConfidenceTier
from core.errors import ExtractionError
from core.rules import RuleMatch
from models.need_analysis import NeedAnalysisProfile
from ingest.types import ContentBlock, StructuredDocument
from wizard import (
    on_file_uploaded,
    on_url_changed,
    _field_lock_config,
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


class _DummySpinner:
    """Minimal spinner context used to bypass Streamlit UI rendering."""

    def __enter__(self) -> None:
        return None

    def __exit__(self, exc_type, exc, tb) -> None:  # pragma: no cover - interface only
        return None


def _prepare_minimal_extraction(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub heavy extraction dependencies to exercise auto re-ask flows."""

    sample_payload = NeedAnalysisProfile().model_dump()

    monkeypatch.setattr("wizard.apply_rules", lambda *_: {})
    monkeypatch.setattr("wizard.matches_to_patch", lambda *_: {})
    monkeypatch.setattr("wizard.build_rule_metadata", lambda *_: {})
    monkeypatch.setattr("wizard._annotate_rule_metadata", lambda *a, **k: {})
    monkeypatch.setattr("wizard._ensure_mapping", lambda value: dict(value or {}))
    monkeypatch.setattr("wizard.extract_json", lambda *a, **k: json.dumps(sample_payload))

    def _coerce(_: dict) -> NeedAnalysisProfile:
        return NeedAnalysisProfile()

    monkeypatch.setattr("wizard.coerce_and_fill", _coerce)
    monkeypatch.setattr("wizard.apply_basic_fallbacks", lambda profile, _text, **_: profile)
    monkeypatch.setattr("wizard.search_occupations", lambda *a, **k: [])
    monkeypatch.setattr("wizard.classify_occupation", lambda *a, **k: None)
    monkeypatch.setattr("wizard.get_essential_skills", lambda *a, **k: [])
    monkeypatch.setattr("wizard._refresh_esco_skills", lambda *a, **k: None)
    monkeypatch.setattr("wizard._update_section_progress", lambda: (None, []))


def _patch_onboarding_streamlit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch Streamlit calls used inside :func:`_step_onboarding`."""

    def fake_radio(label, options, *, key, **kwargs):
        if key == UIKeys.LANG_SELECT:
            # keep current language default
            st.session_state[key] = st.session_state.get(key, options[0])
            return st.session_state[key]
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

    def fake_text_input(label, value="", *, key=None, on_change=None, **kwargs):
        if key is not None and key not in st.session_state:
            st.session_state[key] = value
        return st.session_state.get(key, value)

    def fake_text_area(label, value="", *, key=None, on_change=None, **kwargs):
        if key is not None and key not in st.session_state:
            st.session_state[key] = value
        return st.session_state.get(key, value)

    monkeypatch.setattr(st, "radio", fake_radio)
    monkeypatch.setattr(st, "markdown", lambda *a, **k: None)
    monkeypatch.setattr(st, "subheader", lambda *a, **k: None)
    monkeypatch.setattr(st, "divider", lambda *a, **k: None)
    monkeypatch.setattr(st, "columns", fake_columns)
    monkeypatch.setattr(st, "info", lambda *a, **k: None)
    monkeypatch.setattr(st, "file_uploader", lambda *a, **k: None)
    monkeypatch.setattr(st, "caption", lambda *a, **k: None)
    monkeypatch.setattr(st, "tabs", fake_tabs)
    monkeypatch.setattr(st, "text_input", fake_text_input)
    monkeypatch.setattr(st, "text_area", fake_text_area)
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


@pytest.mark.parametrize(
    ("lang", "error_message", "expected_text"),
    [
        ("de", "File too large for processing", "Datei ist zu groß. Maximale Größe: 20 MB."),
        ("en", "File too large for processing", "File is too large. Maximum size: 20 MB."),
        (
            "de",
            "Requires OCR support for scanned input",
            "Datei konnte nicht gelesen werden. Prüfen Sie, ob es sich um ein gescanntes PDF handelt und installieren Sie ggf. OCR-Abhängigkeiten.",
        ),
        (
            "en",
            "Requires OCR support for scanned input",
            "Failed to read file. If this is a scanned PDF, install OCR dependencies or check the file quality.",
        ),
        (
            "de",
            "File could not be read, possibly scanned PDF",
            "Datei konnte nicht gelesen werden. Prüfen Sie, ob es sich um ein gescanntes PDF handelt und installieren Sie ggf. OCR-Abhängigkeiten.",
        ),
        (
            "en",
            "File could not be read, possibly scanned PDF",
            "Failed to read file. If this is a scanned PDF, install OCR dependencies or check the file quality.",
        ),
    ],
)
def test_on_file_uploaded_shows_localized_errors(
    monkeypatch: pytest.MonkeyPatch, lang: str, error_message: str, expected_text: str
) -> None:
    """Known extraction errors should surface localized UI feedback."""

    st.session_state.clear()
    st.session_state.lang = lang
    st.session_state[UIKeys.PROFILE_FILE_UPLOADER] = object()
    st.session_state["__prefill_profile_doc__"] = StructuredDocument(text="old", blocks=[])
    st.session_state[StateKeys.RAW_BLOCKS] = [ContentBlock(type="paragraph", text="old")]

    def raise_value_error(_file: Any) -> StructuredDocument:
        raise ValueError(error_message)

    calls: list[tuple[str, tuple[Any, ...]]] = []

    def spy_display(message: str, *args: Any) -> None:
        calls.append((message, args))

    monkeypatch.setattr("wizard.extract_text_from_file", raise_value_error)
    monkeypatch.setattr("wizard.display_error", spy_display)

    on_file_uploaded()

    assert calls and calls[0][0] == expected_text
    assert calls[0][1][0] == error_message
    assert st.session_state.get("source_error") is True
    assert st.session_state.get("__prefill_profile_doc__") is None
    assert st.session_state[StateKeys.RAW_BLOCKS] == []
    assert st.session_state.get("__run_extraction__") is not True


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


def test_on_url_changed_accepts_query_and_fragment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """URLs with parameters and fragments should be accepted."""

    st.session_state.clear()
    st.session_state.lang = "en"
    url = "https://example.com/path?utm_source=test#details"
    st.session_state[UIKeys.PROFILE_URL_INPUT] = url
    seen: dict[str, str] = {}

    def fake_extract(u: str) -> StructuredDocument:
        seen["url"] = u
        return StructuredDocument(
            text="url text",
            blocks=[ContentBlock(type="paragraph", text="url text")],
        )

    monkeypatch.setattr("wizard.extract_text_from_url", fake_extract)

    on_url_changed()

    assert seen["url"] == url
    assert st.session_state.get("source_error") in (None, False)
    assert st.session_state["__run_extraction__"] is True


def test_on_url_changed_rejects_invalid_schema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Non-HTTP URLs should raise a validation error without fetching."""

    st.session_state.clear()
    st.session_state.lang = "en"
    st.session_state[UIKeys.PROFILE_URL_INPUT] = "ftp://example.com/file"
    errors: list[str] = []

    def fake_error(message, *args, **kwargs):  # pragma: no cover - lambda style
        errors.append(message)

    monkeypatch.setattr("wizard.display_error", fake_error)
    monkeypatch.setattr(
        "wizard.extract_text_from_url",
        lambda _u: (_ for _ in ()).throw(AssertionError("should not fetch")),
    )

    on_url_changed()

    assert st.session_state.get("source_error") is True
    assert st.session_state.get("__run_extraction__") is not True
    assert errors


def test_on_url_changed_sets_summary_on_fetch_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """URL fetch failures should surface a localized summary message."""

    st.session_state.clear()
    st.session_state.lang = "en"
    st.session_state[StateKeys.EXTRACTION_SUMMARY] = {"previous": "summary"}
    st.session_state[UIKeys.PROFILE_URL_INPUT] = "https://invalid.example"
    st.session_state[StateKeys.RAW_BLOCKS] = [ContentBlock(type="paragraph", text="old")]

    errors: list[str] = []

    def fake_error(message: str, *_args: Any, **_kwargs: Any) -> None:
        errors.append(message)

    monkeypatch.setattr("wizard.display_error", fake_error)
    monkeypatch.setattr(
        "wizard.extract_text_from_url",
        lambda _u: (_ for _ in ()).throw(ValueError("failed to fetch URL (status 404)")),
    )

    on_url_changed()

    expected_message = "❌ URL could not be fetched. Please check the address."
    assert errors and errors[0] == expected_message
    assert st.session_state[StateKeys.EXTRACTION_SUMMARY] == expected_message
    assert st.session_state.get("__run_extraction__") is not True
    assert st.session_state.get("source_error") is True
    assert st.session_state[StateKeys.RAW_BLOCKS] == []

    st.session_state[UIKeys.PROFILE_URL_INPUT] = "https://valid.example"

    monkeypatch.setattr(
        "wizard.extract_text_from_url",
        lambda _u: StructuredDocument(
            text="url text",
            blocks=[ContentBlock(type="paragraph", text="url text")],
        ),
    )

    on_url_changed()

    assert st.session_state[StateKeys.EXTRACTION_SUMMARY] == {}
    assert st.session_state.get("source_error") in (None, False)
    assert st.session_state["__prefill_profile_doc__"].text == "url text"
    assert st.session_state["__run_extraction__"] is True


def test_onboarding_transfers_prefill_to_raw_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prefilled text is copied into the RAW_TEXT slot when onboarding runs."""

    st.session_state.clear()
    st.session_state.lang = "en"
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
    monkeypatch.setattr(st, "warning", lambda message, *a, **k: warnings.append(message))

    _maybe_run_extraction({})

    assert captured["text"] == "prefilled"
    assert st.session_state[StateKeys.RAW_TEXT] == "prefilled"
    assert st.session_state[StateKeys.RAW_BLOCKS]
    assert st.session_state[StateKeys.RAW_BLOCKS][0].type == "paragraph"
    assert warnings == []


def test_maybe_run_extraction_preserves_summary_and_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Summary and missing data set during extraction remain available afterwards."""

    st.session_state.clear()
    st.session_state.lang = "en"
    st.session_state.model = "gpt"
    st.session_state[StateKeys.RAW_TEXT] = "Job description"
    st.session_state["__run_extraction__"] = True

    expected_summary = {"summary": "value"}
    expected_missing = ["company.name"]

    def fake_extract(text: str, schema: dict) -> None:
        assert text == "Job description"
        st.session_state[StateKeys.EXTRACTION_SUMMARY] = expected_summary
        st.session_state[StateKeys.EXTRACTION_MISSING] = expected_missing

    monkeypatch.setattr("wizard._extract_and_summarize", fake_extract)
    monkeypatch.setattr("wizard._autodetect_lang", lambda _text: None)
    monkeypatch.setattr(st, "rerun", lambda: None)

    _maybe_run_extraction({})

    assert st.session_state[StateKeys.EXTRACTION_SUMMARY] is expected_summary
    assert st.session_state[StateKeys.EXTRACTION_MISSING] is expected_missing


def test_onboarding_triggers_extraction(monkeypatch: pytest.MonkeyPatch) -> None:
    """When the extraction flag is set the onboarding step should invoke it."""

    st.session_state.clear()
    st.session_state.lang = "en"
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


@pytest.mark.parametrize(
    ("lang", "expected"),
    [
        ("de", "Automatische Extraktion fehlgeschlagen"),
        ("en", "Automatic extraction failed"),
    ],
)
def test_maybe_run_extraction_handles_errors(monkeypatch: pytest.MonkeyPatch, lang: str, expected: str) -> None:
    """Extraction failures should surface localized fallback alerts."""

    st.session_state.clear()
    st.session_state.lang = lang
    st.session_state["__run_extraction__"] = True
    st.session_state["__prefill_profile_doc__"] = StructuredDocument(
        text="Detected text",
        blocks=[ContentBlock(type="paragraph", text="Detected text")],
    )

    monkeypatch.setattr("wizard.clean_structured_document", lambda doc: doc)
    monkeypatch.setattr("wizard._autodetect_lang", lambda _text: None)
    monkeypatch.setattr(st, "rerun", lambda: None)

    def fake_extract(text: str, schema: dict) -> None:
        raise RuntimeError("synthetic failure")

    calls: list[tuple[str, tuple[Any, ...]]] = []

    monkeypatch.setattr("wizard._extract_and_summarize", fake_extract)
    monkeypatch.setattr("wizard.display_error", lambda message, *args: calls.append((message, args)))

    _maybe_run_extraction({})

    assert calls and calls[0][0] == expected
    assert calls[0][1][0] == "synthetic failure"
    assert st.session_state[StateKeys.RAW_TEXT] == "Detected text"
    assert st.session_state[StateKeys.RAW_BLOCKS] == [ContentBlock(type="paragraph", text="Detected text")]
    assert st.session_state.get("__last_extracted_hash__") is None
    assert st.session_state.get("_analyze_attempted") is True
    assert st.session_state.get("source_error") is not True
    summary_message = st.session_state[StateKeys.EXTRACTION_SUMMARY]
    assert isinstance(summary_message, str)
    assert "⚠️" in summary_message
    assert st.session_state[StateKeys.STEPPER_WARNING] == summary_message


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
    monkeypatch.setattr("wizard.apply_basic_fallbacks", lambda p, _t, **_: p)
    monkeypatch.setattr("wizard.classify_occupation", lambda *a, **k: None)
    monkeypatch.setattr("wizard.search_occupations", lambda *a, **k: [])
    monkeypatch.setattr("wizard.get_essential_skills", lambda *a, **k: [])
    _extract_and_summarize("Job text", {})

    data = st.session_state[StateKeys.PROFILE]
    assert data["position"]["occupation_label"] is None
    assert data["requirements"]["hard_skills_required"] == ["Python"]
    assert st.session_state[StateKeys.ESCO_SELECTED_OCCUPATIONS] == []


def test_extract_and_summarize_prefills_gap_analysis_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Raw job text and job title should prefill the gap analysis form."""

    st.session_state.clear()
    st.session_state.lang = "en"
    sample_data = {"position": {"job_title": "Engineer"}}

    monkeypatch.setattr("wizard.extract_json", lambda *a, **k: json.dumps(sample_data))
    monkeypatch.setattr("wizard.coerce_and_fill", NeedAnalysisProfile.model_validate)
    monkeypatch.setattr("wizard.apply_basic_fallbacks", lambda p, _t, **_: p)
    monkeypatch.setattr("wizard.classify_occupation", lambda *a, **k: None)
    monkeypatch.setattr("wizard.search_occupations", lambda *a, **k: [])
    monkeypatch.setattr("wizard.get_essential_skills", lambda *a, **k: [])

    _extract_and_summarize("  Job text  ", {})

    assert st.session_state[StateKeys.GAP_ANALYSIS_TEXT] == "Job text"
    assert st.session_state[StateKeys.GAP_ANALYSIS_TITLE] == "Engineer"


def test_extract_and_summarize_enriches_esco_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Detected job titles should enrich the profile with ESCO metadata."""

    st.session_state.clear()
    st.session_state.lang = "en"
    st.session_state.model = "gpt"
    sample_data = {"position": {"job_title": "Software Engineer"}}
    occupation = {
        "preferredLabel": "Software developer",
        "uri": "https://example.com/esco/123",
        "group": "Information and communications technology professionals",
    }
    skills = ["Programming", "Version control"]

    monkeypatch.setattr("wizard.extract_json", lambda *a, **k: json.dumps(sample_data))
    monkeypatch.setattr("wizard.coerce_and_fill", NeedAnalysisProfile.model_validate)
    monkeypatch.setattr("wizard.apply_basic_fallbacks", lambda p, _t, **_: p)
    monkeypatch.setattr("wizard.classify_occupation", lambda *a, **k: dict(occupation))
    monkeypatch.setattr(
        "wizard.search_occupations",
        lambda *a, **k: [dict(occupation)],
    )
    monkeypatch.setattr("wizard.get_essential_skills", lambda *a, **k: list(skills))

    _extract_and_summarize("Job text", {})

    data = st.session_state[StateKeys.PROFILE]
    assert data["position"]["occupation_label"] == occupation["preferredLabel"]
    assert data["position"]["occupation_uri"] == occupation["uri"]
    assert data["position"]["occupation_group"] == occupation["group"]
    assert st.session_state[StateKeys.UI_ESCO_OCCUPATION_OPTIONS] == [occupation]
    assert st.session_state[StateKeys.ESCO_SELECTED_OCCUPATIONS] == [occupation]
    assert st.session_state[UIKeys.POSITION_ESCO_OCCUPATION] == [occupation["uri"]]
    assert st.session_state[StateKeys.ESCO_SKILLS] == skills
    raw_profile = st.session_state[StateKeys.EXTRACTION_RAW_PROFILE]
    assert raw_profile["position"]["occupation_label"] == occupation["preferredLabel"]
    assert raw_profile["position"]["occupation_uri"] == occupation["uri"]
    assert raw_profile["position"]["occupation_group"] == occupation["group"]


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
    monkeypatch.setattr("wizard.apply_basic_fallbacks", lambda p, _t, **_: p)
    monkeypatch.setattr("wizard.classify_occupation", lambda *a, **k: None)
    monkeypatch.setattr("wizard.get_essential_skills", lambda *a, **k: [])
    _extract_and_summarize("Job text", {})

    metadata = st.session_state[StateKeys.PROFILE_METADATA]
    rag_meta = metadata["rag"]
    assert rag_meta["vector_store_id"] == "vs42"
    assert rag_meta["fields"] == {}
    assert rag_meta["global_context"] == []
    assert rag_meta["answers"] == {}


def test_extract_and_summarize_marks_ai_confidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AI-derived fields should be tagged with the default confidence tier."""

    st.session_state.clear()
    st.session_state.lang = "en"
    st.session_state.model = "gpt"

    sample_data = {
        "position": {"job_title": "Engineer"},
        "company": {"name": "ACME"},
    }

    monkeypatch.setattr("wizard.apply_rules", lambda *_: {})
    monkeypatch.setattr("wizard.extract_json", lambda *a, **k: json.dumps(sample_data))
    monkeypatch.setattr("wizard.coerce_and_fill", NeedAnalysisProfile.model_validate)
    monkeypatch.setattr("wizard.apply_basic_fallbacks", lambda p, _t, **_: p)
    monkeypatch.setattr("wizard.classify_occupation", lambda *a, **k: None)
    monkeypatch.setattr("wizard.get_essential_skills", lambda *a, **k: [])

    _extract_and_summarize("Job text", {})

    metadata = st.session_state[StateKeys.PROFILE_METADATA]
    field_conf = metadata["field_confidence"]
    assert field_conf["position.job_title"]["tier"] == ConfidenceTier.AI_ASSISTED.value
    assert field_conf["position.job_title"]["source"] == "llm"
    assert field_conf["company.name"]["tier"] == ConfidenceTier.AI_ASSISTED.value
    assert field_conf["company.name"]["source"] == "llm"


@pytest.mark.parametrize(
    ("lang", "expected"),
    [
        ("de", "Konnte keine Anschlussfragen erzeugen."),
        ("en", "Could not generate follow-ups automatically."),
    ],
)
def test_extract_and_summarize_auto_reask_warns_on_followup_error(
    monkeypatch: pytest.MonkeyPatch, lang: str, expected: str
) -> None:
    """Auto re-ask should warn when follow-up generation raises an error."""

    st.session_state.clear()
    st.session_state.lang = lang
    st.session_state.model = "gpt"
    st.session_state.auto_reask = True
    st.session_state.vector_store_id = ""
    st.session_state[StateKeys.RAW_BLOCKS] = []
    st.session_state[StateKeys.PROFILE_METADATA] = {}
    st.session_state[StateKeys.FOLLOWUPS] = [{"field": "company.name", "question": "?", "priority": "critical"}]
    st.session_state[StateKeys.RAG_CONTEXT_SKIPPED] = False

    _prepare_minimal_extraction(monkeypatch)
    monkeypatch.setattr(st, "spinner", lambda *a, **k: _DummySpinner())

    warnings: list[str] = []
    monkeypatch.setattr(st, "warning", lambda message, *a, **k: warnings.append(message))

    def failing_followups(*_: Any, **__: Any) -> dict:
        raise RuntimeError("rate limit")

    monkeypatch.setattr(question_logic, "ask_followups", failing_followups)
    monkeypatch.setattr("wizard.ask_followups", failing_followups)

    _extract_and_summarize("Job text", {})

    assert warnings == [expected]
    assert st.session_state[StateKeys.FOLLOWUPS] == [{"field": "company.name", "question": "?", "priority": "critical"}]
    assert st.session_state[StateKeys.RAG_CONTEXT_SKIPPED] is False
    assert st.session_state.get("source_error") is not True


@pytest.mark.parametrize(
    ("lang", "expected", "initial_flag"),
    [
        ("de", "Konnte keine Anschlussfragen erzeugen.", True),
        ("en", "Could not generate follow-ups automatically.", False),
    ],
)
def test_extract_and_summarize_auto_reask_warns_on_invalid_payload(
    monkeypatch: pytest.MonkeyPatch, lang: str, expected: str, initial_flag: bool
) -> None:
    """Malformed follow-up payloads should trigger the localized warning."""

    st.session_state.clear()
    st.session_state.lang = lang
    st.session_state.model = "gpt"
    st.session_state.auto_reask = True
    st.session_state.vector_store_id = ""
    st.session_state[StateKeys.RAW_BLOCKS] = []
    st.session_state[StateKeys.PROFILE_METADATA] = {}
    st.session_state[StateKeys.FOLLOWUPS] = [{"field": "position.job_title", "question": "?", "priority": "critical"}]
    st.session_state[StateKeys.RAG_CONTEXT_SKIPPED] = initial_flag

    _prepare_minimal_extraction(monkeypatch)
    monkeypatch.setattr(st, "spinner", lambda *a, **k: _DummySpinner())

    warnings: list[str] = []
    monkeypatch.setattr(st, "warning", lambda message, *a, **k: warnings.append(message))

    def malformed_followups(*_: Any, **__: Any) -> list[str]:
        return ["not-a-dict"]

    monkeypatch.setattr(question_logic, "ask_followups", malformed_followups)
    monkeypatch.setattr("wizard.ask_followups", malformed_followups)

    _extract_and_summarize("Job text", {})

    assert warnings == [expected]
    assert st.session_state[StateKeys.FOLLOWUPS] == [
        {"field": "position.job_title", "question": "?", "priority": "critical"}
    ]
    assert st.session_state[StateKeys.RAG_CONTEXT_SKIPPED] is initial_flag
    assert st.session_state.get("source_error") is not True


def test_extract_and_summarize_uses_rules_on_llm_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rule-based matches should populate the profile when the LLM fails."""

    st.session_state.clear()
    st.session_state.lang = "en"
    st.session_state.model = "gpt"
    st.session_state.auto_reask = False
    st.session_state.vector_store_id = ""
    st.session_state[StateKeys.RAW_BLOCKS] = []
    st.session_state[StateKeys.PROFILE_METADATA] = {}
    st.session_state[StateKeys.FOLLOWUPS] = []
    st.session_state[StateKeys.RAG_CONTEXT_SKIPPED] = False

    company_match = RuleMatch(
        field="company.name",
        value="ACME GmbH",
        confidence=0.95,
        source_text="ACME GmbH",
        rule="test.company",
    )
    title_match = RuleMatch(
        field="position.job_title",
        value="AI Engineer",
        confidence=0.9,
        source_text="AI Engineer",
        rule="test.title",
    )

    def _matches(*_: Any) -> Mapping[str, RuleMatch]:
        return {"company.name": company_match, "position.job_title": title_match}

    monkeypatch.setattr("wizard.apply_rules", _matches)
    monkeypatch.setattr("wizard._annotate_rule_metadata", lambda *a, **k: {})
    monkeypatch.setattr("wizard._ensure_mapping", lambda value: dict(value or {}))

    def _raise_extraction(*_: Any, **__: Any) -> str:
        raise ExtractionError("LLM returned empty response")

    monkeypatch.setattr("wizard.extract_json", _raise_extraction)
    monkeypatch.setattr("wizard.search_occupations", lambda *a, **k: [])
    monkeypatch.setattr("wizard.classify_occupation", lambda *a, **k: None)
    monkeypatch.setattr("wizard.get_essential_skills", lambda *a, **k: [])
    monkeypatch.setattr("wizard._refresh_esco_skills", lambda *a, **k: None)
    monkeypatch.setattr("wizard.ask_followups", lambda *a, **k: {"questions": []})
    monkeypatch.setattr("wizard.apply_basic_fallbacks", lambda profile, *_args, **_kwargs: profile)
    monkeypatch.setattr("wizard._update_section_progress", lambda: (None, []))

    _extract_and_summarize("Job text", {})

    profile = st.session_state[StateKeys.PROFILE]
    assert profile["company"]["name"] == "ACME GmbH"
    assert profile["position"]["job_title"] == "AI Engineer"
    metadata = st.session_state[StateKeys.PROFILE_METADATA]
    assert metadata["llm_errors"]["extraction"] == "LLM returned empty response"
    assert "position.job_title" not in st.session_state[StateKeys.EXTRACTION_MISSING]


def test_extract_and_summarize_passes_locked_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rule-locked fields and document source should be forwarded as hints."""

    st.session_state.clear()
    st.session_state.lang = "en"
    st.session_state.model = "gpt"
    st.session_state[StateKeys.RAW_BLOCKS] = []
    st.session_state[StateKeys.PROFILE_METADATA] = {
        "rules": {
            "position.job_title": {"value": "Locked Engineer"},
            "company.name": {"value": "Locked Corp"},
        },
        "locked_fields": ["position.job_title", "company.name"],
        "high_confidence_fields": ["position.job_title", "company.name"],
    }
    st.session_state["__prefill_profile_doc__"] = StructuredDocument(
        text="Job text",
        blocks=[],
        source="https://example.com/job",
    )

    captured: dict[str, str | None] = {}

    def fake_extract_json(
        text: str,
        *,
        title: str | None = None,
        company: str | None = None,
        url: str | None = None,
        locked_fields: dict[str, str] | None = None,
        minimal: bool = False,
    ) -> str:
        captured["title"] = title
        captured["company"] = company
        captured["url"] = url
        captured["locked_fields"] = locked_fields or {}
        return json.dumps({"position": {"job_title": "Engineer"}})

    monkeypatch.setattr("wizard.extract_json", fake_extract_json)
    monkeypatch.setattr("wizard.coerce_and_fill", NeedAnalysisProfile.model_validate)
    monkeypatch.setattr("wizard.apply_basic_fallbacks", lambda p, _t, **_: p)
    monkeypatch.setattr("wizard.classify_occupation", lambda *a, **k: None)
    monkeypatch.setattr("wizard.get_essential_skills", lambda *a, **k: [])

    _extract_and_summarize("Job text", {})

    assert captured["title"] == "Locked Engineer"
    assert captured["company"] == "Locked Corp"
    assert captured["url"] == "https://example.com/job"
    assert captured["locked_fields"] == {
        "position.job_title": "Locked Engineer",
        "company.name": "Locked Corp",
    }


def test_field_lock_config_shows_rule_indicator() -> None:
    """Rule tiers should be reflected in the widget label and help text."""

    st.session_state.clear()
    st.session_state.lang = "en"
    st.session_state[StateKeys.PROFILE_METADATA] = {
        "locked_fields": ["company.contact_email"],
        "high_confidence_fields": ["company.contact_email"],
        "field_confidence": {
            "company.contact_email": {
                "tier": ConfidenceTier.RULE_STRONG.value,
                "source": "rule",
                "score": 0.98,
            }
        },
    }

    config = _field_lock_config("company.contact_email", "Email")
    assert config["confidence_tier"] == ConfidenceTier.RULE_STRONG.value
    assert "🔎" in config["confidence_icon"]
    assert "Pattern match" in config["confidence_message"]
    assert config["confidence_source"] == "rule"
    assert "🔒" in config["label"]


def test_field_lock_config_shows_ai_indicator() -> None:
    """AI inferred tiers should use the assistant indicator and remain editable."""

    st.session_state.clear()
    st.session_state.lang = "en"
    st.session_state[StateKeys.PROFILE_METADATA] = {
        "locked_fields": [],
        "high_confidence_fields": [],
        "field_confidence": {
            "position.job_title": {
                "tier": ConfidenceTier.AI_ASSISTED.value,
                "source": "llm",
                "score": None,
            }
        },
    }

    config = _field_lock_config("position.job_title", "Job title")
    assert config["confidence_tier"] == ConfidenceTier.AI_ASSISTED.value
    assert "🤖" in config["confidence_icon"]
    assert "Inferred by AI" in config["confidence_message"]
    assert config["confidence_source"] == "llm"
    assert config.get("unlocked") is True
