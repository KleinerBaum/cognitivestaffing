from __future__ import annotations

import streamlit as st

from utils.usage import build_usage_markdown, build_usage_rows, usage_totals


def test_build_usage_markdown_includes_tasks() -> None:
    st.session_state.clear()
    st.session_state["lang"] = "en"
    usage = {
        "input_tokens": 12,
        "output_tokens": 24,
        "by_task": {
            "extraction": {"input": 6, "output": 12},
            "job_ad": {"input": 4, "output": 8},
            "salary_estimate": {"input": 2, "output": 4},
        },
    }

    markdown = build_usage_markdown(usage)
    assert markdown is not None

    lines = markdown.splitlines()
    # Header + separator + three rows expected
    assert len(lines) == 5
    assert "Task" in lines[0]
    assert "Extraction" in markdown
    assert "Job ad" in markdown
    assert "Salary estimate" in markdown

    # Ensure rows are sorted by total tokens (descending)
    first_row = lines[2]
    assert "Extraction" in first_row


def test_usage_rows_and_totals_handle_missing_sections() -> None:
    st.session_state.clear()
    st.session_state["lang"] = "de"
    usage = {"input_tokens": "3", "output_tokens": "7", "tasks": {}}

    rows = build_usage_rows(usage)
    assert rows == []
    totals = usage_totals(usage)
    assert totals == (3, 7, 10)
