"""Tests for ``wizard.state_sync`` helpers."""

from __future__ import annotations

from typing import Any

import streamlit as st

import wizard.state_sync as state_sync


def test_iter_profile_scalars_skips_nested_structures() -> None:
    data = {
        "company": {"name": "Acme", "locations": ["Berlin"]},
        "meta": {"empty": None},
    }
    pairs = dict(state_sync.iter_profile_scalars(data))
    assert pairs["company.name"] == "Acme"
    assert "company.locations" not in pairs


def test_prime_widget_state_from_profile_clears_empty_values() -> None:
    st.session_state.clear()
    data: dict[str, Any] = {
        "company": {"name": "Acme", "contact_email": ""},
        "meta": {"notes": None},
    }
    state_sync.prime_widget_state_from_profile(data)
    assert st.session_state["company.name"] == "Acme"
    assert "company.contact_email" not in st.session_state
    assert "meta.notes" not in st.session_state
