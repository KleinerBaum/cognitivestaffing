import json
import sys
from pathlib import Path

import pytest
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from constants.keys import StateKeys, UIKeys
from core.confidence import ConfidenceTier
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
    monkeypatch.setattr("wizard.apply_basic_fallbacks", lambda p, _t, **_: p)
    monkeypatch.setattr("wizard.classify_occupation", lambda *a, **k: None)
    monkeypatch.setattr("wizard.search_occupations", lambda *a, **k: [])
    monkeypatch.setattr("wizard.get_essential_skills", lambda *a, **k: [])
    _extract_and_summarize("Job text", {})

    data = st.session_state[StateKeys.PROFILE]
    assert data["position"]["occupation_label"] is None
    assert data["requirements"]["hard_skills_required"] == ["Python"]
    assert st.session_state[StateKeys.ESCO_SELECTED_OCCUPATIONS] == []


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
    assert st.session_state[StateKeys.ESCO_OCCUPATION_OPTIONS] == [occupation]
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
