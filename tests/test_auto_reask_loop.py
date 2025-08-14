import sys
from pathlib import Path

import streamlit as st

sys.path.append(str(Path(__file__).resolve().parents[1]))
import wizard


def test_auto_mode_generates_next_question(monkeypatch) -> None:
    """Auto mode should fetch the next follow-up question automatically."""
    st.session_state.clear()
    st.session_state["lang"] = "en"
    st.session_state["auto_mode"] = True
    st.session_state["followup_questions"] = []
    # Leave a critical field blank so a question is needed
    st.session_state["company.name"] = ""

    called: dict[str, int | None] = {}

    def fake_generate(jd, num_questions=None, **_):
        called["num_questions"] = num_questions
        return [{"field": "company.name", "question": "Name?"}]

    monkeypatch.setattr(wizard, "generate_followup_questions", fake_generate)
    monkeypatch.setattr(st, "checkbox", lambda *a, **k: True)
    monkeypatch.setattr(st, "caption", lambda *a, **k: None)
    monkeypatch.setattr(st, "text_input", lambda *a, **k: "")

    wizard.render_followups_for(["company.name"])

    assert called["num_questions"] == 1
    assert st.session_state["followup_questions"]
