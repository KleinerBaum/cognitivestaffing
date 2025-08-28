import streamlit as st

from wizard import _field_label


def test_field_label_known() -> None:
    st.session_state.lang = "en"
    assert _field_label("company.name") == "Company name"


def test_field_label_fallback() -> None:
    st.session_state.lang = "en"
    assert _field_label("compensation.salary_min") == "Compensation Salary Min"
