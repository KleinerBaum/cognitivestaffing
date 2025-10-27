from __future__ import annotations

from collections.abc import Callable, Iterator

import pytest
import streamlit as st

from components import widget_factory
from constants.keys import StateKeys
from state import ensure_state
from wizard._logic import get_value


@pytest.fixture(autouse=True)
def _reset_state() -> Iterator[None]:
    """Provide a clean Streamlit session for every widget factory test."""

    st.session_state.clear()
    ensure_state()
    yield
    st.session_state.clear()


def test_bindings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Factories should read defaults and update the profile on change."""

    profile = st.session_state[StateKeys.PROFILE]
    profile["company"]["name"] = "ACME"
    profile["position"]["seniority_level"] = "Senior"

    callbacks: dict[str, Callable[[], None]] = {}

    def fake_text_input(
        label: str,
        *,
        value: str = "",
        key: str | None = None,
        on_change: Callable[[], None] | None = None,
        **_: object,
    ) -> str:
        assert label == "Company"
        assert value == "ACME"
        assert key == "company.name"
        st.session_state[key] = value
        if on_change is not None:
            callbacks[key] = on_change
        return value

    monkeypatch.setattr(st, "text_input", fake_text_input)

    result = widget_factory.text_input("company.name", "Company")
    assert result == "ACME"

    st.session_state["company.name"] = "ACME GmbH"
    callbacks["company.name"]()
    assert get_value("company.name") == "ACME GmbH"

    options = ["Junior", "Mid", "Senior"]

    def fake_selectbox(
        label: str,
        entries: list[str],
        *,
        index: int = 0,
        key: str | None = None,
        on_change: Callable[[], None] | None = None,
        **_: object,
    ) -> str:
        assert label == "Seniority"
        assert entries == options
        assert index == 2
        assert key == "position.seniority_level"
        choice = entries[index]
        st.session_state[key] = choice
        if on_change is not None:
            callbacks[key] = on_change
        return choice

    monkeypatch.setattr(st, "selectbox", fake_selectbox)

    selected = widget_factory.select("position.seniority_level", "Seniority", options)
    assert selected == "Senior"

    st.session_state["position.seniority_level"] = "Mid"
    callbacks["position.seniority_level"]()
    assert get_value("position.seniority_level") == "Mid"
