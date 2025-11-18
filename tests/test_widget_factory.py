from __future__ import annotations

from collections.abc import Callable, Iterator
import importlib
from typing import Any

import pytest
import streamlit as st

from components import widget_factory
from constants.keys import ProfilePaths, StateKeys
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


def test_text_input_syncs_when_profile_updates(monkeypatch: pytest.MonkeyPatch) -> None:
    """Widget factory should push profile changes back into widget state."""

    profile = st.session_state[StateKeys.PROFILE]
    profile["company"]["hq_location"] = ""

    captured_values: list[str] = []

    def fake_text_input(
        label: str,
        *,
        value: str = "",
        key: str | None = None,
        on_change: Callable[[], None] | None = None,
        **_: object,
    ) -> str:
        captured_values.append(value)
        if key is not None:
            st.session_state[key] = value
        if on_change is not None:
            on_change()
        return value

    monkeypatch.setattr(st, "text_input", fake_text_input)

    widget_factory.text_input("company.hq_location", "Headquarters")
    assert captured_values[-1] == ""

    profile["company"]["hq_location"] = "Berlin, DE"

    widget_factory.text_input("company.hq_location", "Headquarters")
    assert captured_values[-1] == "Berlin, DE"


def test_autofill_accept_updates_profile_and_requests_rerun(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Accepting an autofill suggestion updates the profile and reruns."""

    profile = st.session_state[StateKeys.PROFILE]
    profile["company"]["hq_location"] = ""

    def fake_text_input(
        label: str,
        *,
        value: str = "",
        key: str | None = None,
        on_change: Callable[[], None] | None = None,
        **_: object,
    ) -> str:
        if key is not None:
            st.session_state[key] = value
        return value

    monkeypatch.setattr(st, "text_input", fake_text_input)
    widget_factory.text_input("company.hq_location", "Headquarters")

    class _Container:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class _Column:
        def __init__(self, clicked: bool) -> None:
            self._clicked = clicked

        def button(self, *_: object, **__: object) -> bool:
            return self._clicked

    monkeypatch.setattr(st, "container", lambda **_: _Container())
    monkeypatch.setattr(st, "columns", lambda *_args, **_kwargs: (_Column(True), _Column(False)))
    monkeypatch.setattr(st, "markdown", lambda *_, **__: None)
    monkeypatch.setattr(st, "caption", lambda *_, **__: None)
    monkeypatch.setattr(st, "toast", lambda *_, **__: None)

    rerun_called = False

    def fake_rerun() -> None:
        nonlocal rerun_called
        rerun_called = True
        raise RuntimeError("rerun triggered")

    monkeypatch.setattr(st, "rerun", fake_rerun)

    module = importlib.import_module("wizard")
    render_autofill: Any = getattr(module, "_render_autofill_suggestion")

    with pytest.raises(RuntimeError, match="rerun triggered"):
        render_autofill(
            field_path="company.hq_location",
            suggestion="Berlin, DE",
            title="HQ",
            description="Suggested",
        )

    assert rerun_called is True
    assert get_value("company.hq_location") == "Berlin, DE"

    widget_factory.text_input("company.hq_location", "Headquarters")

    assert st.session_state["company.hq_location"] == "Berlin, DE"


def test_select_converts_use_container_width(monkeypatch: pytest.MonkeyPatch) -> None:
    """Deprecated width flag is translated into the modern ``width`` kwarg."""

    profile = st.session_state[StateKeys.PROFILE]
    profile.setdefault("position", {})["seniority_level"] = "Mid"

    options = ["Junior", "Mid", "Senior"]
    received_kwargs: dict[str, Any] = {}

    def fake_selectbox(
        label: str,
        entries: list[str],
        *,
        index: int = 0,
        key: str | None = None,
        on_change: Callable[[], None] | None = None,
        **kwargs: Any,
    ) -> str:
        assert label == "Seniority"
        assert entries == options
        received_kwargs.update(kwargs)
        choice = entries[index]
        if key is not None:
            st.session_state[key] = choice
        if on_change is not None:
            on_change()
        return choice

    monkeypatch.setattr(st, "selectbox", fake_selectbox)

    widget_factory.select(
        "position.seniority_level",
        "Seniority",
        options,
        use_container_width=True,
    )

    assert received_kwargs["width"] == "stretch"
    assert "use_container_width" not in received_kwargs


def test_select_prefers_explicit_width(monkeypatch: pytest.MonkeyPatch) -> None:
    """Explicit ``width`` values override deprecated hints."""

    profile = st.session_state[StateKeys.PROFILE]
    profile.setdefault("position", {})["seniority_level"] = "Mid"

    options = ["Junior", "Mid", "Senior"]
    received_kwargs: dict[str, Any] = {}

    def fake_selectbox(
        label: str,
        entries: list[str],
        *,
        index: int = 0,
        key: str | None = None,
        on_change: Callable[[], None] | None = None,
        **kwargs: Any,
    ) -> str:
        received_kwargs.update(kwargs)
        choice = entries[index]
        if key is not None:
            st.session_state[key] = choice
        if on_change is not None:
            on_change()
        return choice

    monkeypatch.setattr(st, "selectbox", fake_selectbox)

    widget_factory.select(
        "position.seniority_level",
        "Seniority",
        options,
        use_container_width=True,
        width="content",
    )

    assert received_kwargs["width"] == "content"


def test_text_input_preserves_manual_state_without_callbacks(monkeypatch: pytest.MonkeyPatch) -> None:
    """Widgets without callbacks must keep user-provided session state."""

    profile = st.session_state[StateKeys.PROFILE]
    profile["company"]["name"] = "ACME"
    st.session_state[ProfilePaths.COMPANY_NAME] = "Typed"

    def fake_text_input(
        label: str,
        *,
        value: str = "",
        key: str | None = None,
        **_: object,
    ) -> str:
        assert label == "Company"
        assert value == "ACME"
        assert key == ProfilePaths.COMPANY_NAME
        return st.session_state.get(key, value)

    result = widget_factory.text_input(
        ProfilePaths.COMPANY_NAME,
        "Company",
        allow_callbacks=False,
        sync_session_state=False,
        widget_factory=fake_text_input,
    )

    assert result == "Typed"
    assert st.session_state[ProfilePaths.COMPANY_NAME] == "Typed"
