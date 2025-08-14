import json

import streamlit as st
import wizard


def test_normalise_state_populates_aliases() -> None:
    st.session_state.clear()
    st.session_state["position.job_title"] = "Engineer"
    st.session_state["responsibilities.items"] = "Task A\nTask B"
    st.session_state["employment.job_type"] = "full time"
    st.session_state["employment.work_policy"] = "Remote"
    wizard.normalise_state()
    assert st.session_state["tasks"] == "Task A\nTask B"
    assert st.session_state["contract_type"] == "Full-time"
    assert st.session_state["remote_policy"] == "Remote"
    jd = json.loads(st.session_state["validated_json"])
    assert jd["employment"]["job_type"] == "Full-time"
    assert jd["employment"]["work_policy"] == "Remote"
    assert jd["responsibilities"]["items"] == ["Task A", "Task B"]


def test_run_extraction_flow(monkeypatch) -> None:
    st.session_state.clear()
    st.session_state["uploaded_text"] = "Example text"
    st.session_state["llm_model"] = "gpt-4"

    monkeypatch.setattr(wizard, "build_extract_messages", lambda text: [])
    monkeypatch.setattr(
        wizard, "build_extraction_function", lambda: {"name": "extract"}
    )

    def fake_call_chat_api(*args, **kwargs):
        return json.dumps(
            {
                "company": {"name": "ACME"},
                "position": {"job_title": "Engineer"},
                "employment": {"job_type": "full-time", "work_policy": "Remote"},
                "responsibilities": {"items": ["Build things"]},
            }
        )

    monkeypatch.setattr(wizard, "call_chat_api", fake_call_chat_api)
    monkeypatch.setattr(wizard, "generate_followup_questions", lambda *a, **k: [])
    monkeypatch.setattr(
        wizard.esco_utils,
        "classify_occupation",
        lambda *a, **k: {"preferredLabel": "Engineer", "group": "123"},
    )
    monkeypatch.setattr(st, "warning", lambda *a, **k: None)
    monkeypatch.setattr(st, "error", lambda *a, **k: None)

    wizard._run_extraction("en")

    assert st.session_state["company.name"] == "ACME"
    assert st.session_state["position.job_title"] == "Engineer"
    assert st.session_state["employment.work_policy"] == "Remote"
    assert st.session_state["responsibilities.items"] == "Build things"
    assert st.session_state["tasks"] == "Build things"
    assert st.session_state["contract_type"] == "Full-time"
    assert st.session_state["remote_policy"] == "Remote"
    assert st.session_state["extraction_success"] is True
