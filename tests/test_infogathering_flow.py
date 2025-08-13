"""Integration test for info-gathering flow with mocked external APIs."""

import json
from contextlib import contextmanager

import streamlit as st
import wizard
import openai_utils


def test_info_gathering_flow(monkeypatch) -> None:
    """Simulate extraction, navigation, and generation without external services."""
    st.session_state.clear()
    st.session_state["uploaded_text"] = (
        "ACME Corp is hiring a Software Engineer.\n" "Responsibilities: Build things."
    )
    st.session_state["llm_model"] = "gpt-4"
    st.session_state["lang"] = "en"

    # Stub Streamlit UI helpers
    monkeypatch.setattr(st, "header", lambda *a, **k: None)
    monkeypatch.setattr(st, "subheader", lambda *a, **k: None)
    monkeypatch.setattr(st, "write", lambda *a, **k: None)
    monkeypatch.setattr(st, "caption", lambda *a, **k: None)
    monkeypatch.setattr(st, "markdown", lambda *a, **k: None)
    monkeypatch.setattr(st, "image", lambda *a, **k: None)
    monkeypatch.setattr(st, "success", lambda *a, **k: None)
    monkeypatch.setattr(st, "warning", lambda *a, **k: None)
    monkeypatch.setattr(st, "error", lambda *a, **k: None)
    monkeypatch.setattr(st, "rerun", lambda: None)

    @contextmanager
    def fake_spinner(*_a, **_k):
        yield

    monkeypatch.setattr(st, "spinner", fake_spinner)

    # Avoid complex widgets during tests
    monkeypatch.setattr(wizard, "render_extraction_summary", lambda *_a, **_k: None)
    monkeypatch.setattr(wizard, "render_followups_for", lambda *_a, **_k: None)
    monkeypatch.setattr(wizard, "generate_followup_questions", lambda *_a, **_k: [])
    monkeypatch.setattr(wizard.esco_utils, "classify_occupation", lambda *_a, **_k: {})
    monkeypatch.setattr(wizard, "editable_draggable_list", lambda *_a, **_k: None)

    # Mock OpenAI extraction call
    def fake_extract(*_a, **_k):
        return json.dumps(
            {
                "company": {"name": "ACME Corp"},
                "position": {
                    "job_title": "Software Engineer",
                    "role_summary": "Build cool stuff",
                },
                "employment": {"job_type": "full-time", "work_policy": "Remote"},
                "responsibilities": {"items": ["Build things"]},
            }
        )

    monkeypatch.setattr(wizard, "call_chat_api", fake_extract)
    monkeypatch.setattr(wizard, "build_extract_messages", lambda text: [])
    monkeypatch.setattr(
        wizard, "build_extraction_function", lambda: {"name": "extract"}
    )

    wizard._run_extraction("en")

    assert st.session_state["company.name"] == "ACME Corp"
    assert st.session_state["position.job_title"] == "Software Engineer"
    assert st.session_state["responsibilities.items"] == "Build things"

    st.session_state["extraction_complete"] = True

    def start_button(label, **_k):
        return label.startswith("🚀 Start Discovery")

    monkeypatch.setattr(st, "button", start_button)
    wizard.start_discovery_page()
    assert st.session_state["current_section"] == 2

    # Reset button to no-ops and stub inputs
    monkeypatch.setattr(st, "button", lambda *_a, **_k: False)
    monkeypatch.setattr(st, "text_input", lambda _l, value="", **_k: value)
    monkeypatch.setattr(st, "text_area", lambda _l, value="", **_k: value)
    monkeypatch.setattr(
        st, "selectbox", lambda _l, options, index=0, **_k: options[index]
    )

    wizard.company_information_page()
    assert st.session_state["company.name"] == "ACME Corp"
    wizard.role_description_page()
    assert st.session_state["position.job_title"] == "Software Engineer"
    wizard.task_scope_page()
    assert st.session_state["responsibilities.items"] == "Build things"

    captured: dict[str, str] = {}

    def fake_generate(messages, **_k):
        captured["prompt"] = messages[0]["content"]
        return "Job Ad"

    monkeypatch.setattr(openai_utils, "call_chat_api", fake_generate)
    output = openai_utils.generate_job_ad(dict(st.session_state))
    assert output == "Job Ad"
    prompt = captured["prompt"]
    assert "Job Title: Software Engineer" in prompt
    assert "Company: ACME Corp" in prompt
    assert "Key Responsibilities: Build things" in prompt
