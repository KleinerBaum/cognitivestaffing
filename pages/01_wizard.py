"""Streamlit wizard for Vacalyser job analysis."""

from __future__ import annotations

import os
import tempfile

import streamlit as st

from core.schema import ALL_FIELDS, ALIASES, LIST_FIELDS
from core.ss_bridge import from_session_state, to_session_state
from ingest import read_job_text
from llm.client import extract_json
from utils.json_parse import parse_extraction


def _normalise_state() -> None:
    """Normalise session state to the latest schema.

    Converts deprecated alias keys to their canonical counterparts and
    ensures list fields use newline separation for text areas.
    """
    if any(alias in st.session_state for alias in ALIASES):
        jd = from_session_state(st.session_state)
        to_session_state(jd, st.session_state)


def _run_extraction(debug: bool) -> None:
    """Execute the extraction pipeline and update session state.

    Args:
        debug: Whether to enable verbose debugging output.
    """
    if debug:
        os.environ["VACAYSER_DEBUG"] = "1"
    else:
        os.environ.pop("VACAYSER_DEBUG", None)

    uploaded = st.session_state.get("uploaded_file")
    files: list[str] = []
    if uploaded:
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(uploaded.getvalue())
            tmp.flush()
            files.append(tmp.name)

    url = st.session_state.get("input_url") or None
    text = read_job_text(files, url=url)
    title = st.session_state.get("job_title") or None

    try:
        raw = extract_json(text, title, url)
        jd = parse_extraction(raw)
    except Exception as exc:  # pragma: no cover - network/LLM errors
        st.session_state["extraction_error"] = str(exc)
        return

    to_session_state(jd, st.session_state)
    st.session_state["validated_json"] = jd.model_dump_json(
        indent=2, ensure_ascii=False
    )
    st.session_state.pop("extraction_error", None)


_normalise_state()

st.title("Vacalyser Wizard")

st.text_input("Job Title", key="job_title")
st.text_input("Job Ad URL", key="input_url")
st.file_uploader("Upload Job Ad", type=["pdf", "docx", "txt"], key="uploaded_file")

debug_mode = st.checkbox("Debug mode", key="debug_mode")
col1, col2 = st.columns(2)
with col1:
    if st.button("Analyze"):
        _run_extraction(debug_mode)
with col2:
    if st.button("Retry extraction"):
        _run_extraction(debug_mode)

if st.session_state.get("extraction_error"):
    st.error(st.session_state["extraction_error"])

if st.session_state.get("validated_json"):
    st.subheader("Extracted Fields")
    for field in ALL_FIELDS:
        if field == "schema_version":
            continue
        label = field.replace("_", " ").title()
        if field in LIST_FIELDS:
            st.text_area(label, key=field)
        else:
            st.text_input(label, key=field)

    jd_current = from_session_state(st.session_state)
    json_str = jd_current.model_dump_json(indent=2, ensure_ascii=False)
    with st.expander("Raw JSON"):
        st.code(json_str, language="json")
        st.download_button(
            "Download JSON",
            json_str,
            file_name="vacalyser_extraction.json",
            mime="application/json",
        )
