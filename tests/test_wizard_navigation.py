"""Tests for the streamlined wizard navigation router."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Dict, List, Mapping

import pytest
import streamlit as st

import wizard
from constants.keys import StateKeys
from pages.base import WizardPage
from wizard_router import StepRenderer, WizardContext, WizardRouter


class DummyContainer:
    """Context manager stub for Streamlit containers."""

    def __enter__(self) -> "DummyContainer":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class DummyColumn:
    """Streamlit column stub returning a predefined button response."""

    def __init__(self, response: bool = False) -> None:
        self._response = response

    def button(self, *_args: object, **_kwargs: object) -> bool:
        result = self._response
        self._response = False
        return result

    def write(self, *_args: object, **_kwargs: object) -> None:
        return None

    def markdown(self, *_args: object, **_kwargs: object) -> None:
        return None

    def caption(self, *_args: object, **_kwargs: object) -> None:
        return None

    def __enter__(self) -> "DummyColumn":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


@pytest.fixture(autouse=True)
def clear_session_state() -> None:
    """Ensure a clean ``st.session_state`` before and after every test."""

    st.session_state.clear()
    yield
    st.session_state.clear()


@pytest.fixture()
def query_params(monkeypatch: pytest.MonkeyPatch) -> Dict[str, List[str]]:
    """Provide an isolated query-param store for navigation tests."""

    store: Dict[str, List[str]] = {}

    def fake_get_params() -> Dict[str, List[str]]:
        return {key: list(value) for key, value in store.items()}

    def fake_set_params(**kwargs: Mapping[str, List[str] | str]) -> None:
        store.clear()
        for key, value in kwargs.items():
            if isinstance(value, list):
                store[key] = list(value)
            else:
                store[key] = [str(value)]

    monkeypatch.setattr(st, "experimental_get_query_params", fake_get_params)
    monkeypatch.setattr(st, "experimental_set_query_params", fake_set_params)
    return store


_STEP_DEFINITIONS: tuple[tuple[str, int, bool], ...] = (
    ("intro", 0, False),
    ("company", 1, False),
    ("team", 2, False),
    ("skills", 3, False),
    ("benefits", 4, True),
    ("summary", 6, False),
)


def _build_pages() -> tuple[WizardPage, ...]:
    pages: list[WizardPage] = []
    for key, _legacy_index, allow_skip in _STEP_DEFINITIONS:
        title = key.replace("_", " ").title()
        pages.append(
            WizardPage(
                key=key,
                label=(title, title),
                panel_header=(title, title),
                panel_subheader=(title, title),
                panel_intro_variants=((f"Intro {title}", f"Intro {title}"),),
                required_fields=(),
                summary_fields=(),
                allow_skip=allow_skip,
            )
        )
    return tuple(pages)


def _build_renderers(log: List[str]) -> Dict[str, StepRenderer]:
    renderers: Dict[str, StepRenderer] = {}
    for key, legacy_index, _allow_skip in _STEP_DEFINITIONS:

        def _make_callback(step_key: str) -> Callable[[WizardContext], None]:
            def _callback(_context: WizardContext) -> None:
                log.append(step_key)

            return _callback

        renderers[key] = StepRenderer(callback=_make_callback(key), legacy_index=legacy_index)
    return renderers


def _make_router(
    monkeypatch: pytest.MonkeyPatch,
    query_params: Dict[str, List[str]],
    missing_ref: Dict[str, List[str]],
) -> tuple[WizardRouter, List[str]]:
    render_log: List[str] = []
    pages = _build_pages()
    renderers = _build_renderers(render_log)
    context = WizardContext(schema={}, critical_fields=[])

    def fake_missing() -> List[str]:
        return list(missing_ref["value"])

    monkeypatch.setattr(wizard, "get_missing_critical_fields", fake_missing)

    def resolver(data: Mapping[str, Any], path: str, default: Any | None) -> Any | None:
        cursor: Any = data
        for part in path.split("."):
            if isinstance(cursor, Mapping) and part in cursor:
                cursor = cursor[part]
            else:
                return default
        return cursor

    router = WizardRouter(
        pages=pages,
        renderers=renderers,
        context=context,
        value_resolver=resolver,
    )
    return router, render_log


def test_navigate_updates_state_and_query(monkeypatch: pytest.MonkeyPatch, query_params: Dict[str, List[str]]) -> None:
    """Calling ``navigate`` should update state, params, and trigger rerun."""

    rerun_called = {"value": False}

    def fake_rerun() -> None:
        rerun_called["value"] = True
        raise RuntimeError("rerun")

    monkeypatch.setattr(st, "rerun", fake_rerun)
    missing_ref = {"value": []}
    router, _ = _make_router(monkeypatch, query_params, missing_ref)

    with pytest.raises(RuntimeError):
        router.navigate("company", mark_current_complete=True)

    wizard_state = st.session_state["wizard"]
    assert wizard_state["current_step"] == "company"
    assert query_params["step"] == ["company"]
    assert st.session_state["_wizard_scroll_to_top"] is True
    completed = wizard_state.get("completed_steps", [])
    assert "intro" in completed
    assert rerun_called["value"]


def test_pending_incomplete_jump_redirects_to_first_incomplete(
    monkeypatch: pytest.MonkeyPatch, query_params: Dict[str, List[str]]
) -> None:
    """Pending incomplete jumps should pick the matching legacy step."""

    st.session_state[StateKeys.PENDING_INCOMPLETE_JUMP] = True
    missing_ref = {"value": ["position.job_title"]}
    router, _ = _make_router(monkeypatch, query_params, missing_ref)

    wizard_state = st.session_state["wizard"]
    assert wizard_state["current_step"] == "team"
    assert query_params["step"] == ["team"]
    assert st.session_state["_wizard_scroll_to_top"] is True


def test_run_scroll_inserts_script_on_step_change(
    monkeypatch: pytest.MonkeyPatch, query_params: Dict[str, List[str]]
) -> None:
    """Rendering a new step should emit the scroll-to-top script once."""

    captured_markdown: List[str] = []
    monkeypatch.setattr(st, "markdown", lambda value, **_: captured_markdown.append(value))
    monkeypatch.setattr(st, "caption", lambda *_, **__: None)
    monkeypatch.setattr(st, "warning", lambda *_, **__: None)
    monkeypatch.setattr(st, "container", lambda: DummyContainer())
    monkeypatch.setattr(st, "columns", lambda *_, **__: [DummyColumn(), DummyColumn(), DummyColumn()])
    monkeypatch.setattr(st, "button", lambda *_, **__: False)
    monkeypatch.setattr(st, "rerun", lambda: (_ for _ in ()).throw(AssertionError("rerun not expected")))

    missing_ref = {"value": []}
    router, _ = _make_router(monkeypatch, query_params, missing_ref)
    st.session_state["lang"] = "de"

    router.run()

    scripts = [entry for entry in captured_markdown if "<script>" in entry]
    assert scripts, "Expected scroll script to be injected"
    assert "scrollTo" in scripts[-1]
    assert "_wizard_scroll_to_top" not in st.session_state


def test_skip_marks_step_completed_and_sets_query(
    monkeypatch: pytest.MonkeyPatch, query_params: Dict[str, List[str]]
) -> None:
    """Skipping an optional step should mark it as completed and move forward."""

    sequence = iter([False, True])  # Next button -> False, Skip button -> True

    def fake_button(*_args: object, **_kwargs: object) -> bool:
        try:
            return next(sequence)
        except StopIteration:
            return False

    monkeypatch.setattr(st, "button", fake_button)
    monkeypatch.setattr(st, "columns", lambda *_, **__: [DummyColumn(), DummyColumn(), DummyColumn()])
    monkeypatch.setattr(st, "markdown", lambda *_, **__: None)
    monkeypatch.setattr(st, "caption", lambda *_, **__: None)
    monkeypatch.setattr(st, "warning", lambda *_, **__: None)
    monkeypatch.setattr(st, "container", lambda: DummyContainer())

    class RerunTriggered(Exception):
        pass

    monkeypatch.setattr(st, "rerun", lambda: (_ for _ in ()).throw(RerunTriggered()))

    missing_ref = {"value": []}
    router, _ = _make_router(monkeypatch, query_params, missing_ref)
    router._state["current_step"] = "benefits"
    query_params["step"] = ["benefits"]

    with pytest.raises(RerunTriggered):
        router.run()

    wizard_state = st.session_state["wizard"]
    assert wizard_state["current_step"] == "summary"
    assert query_params["step"] == ["summary"]
    assert "benefits" in wizard_state.get("completed_steps", [])
    assert "benefits" in wizard_state.get("skipped_steps", [])
    assert st.session_state["_wizard_scroll_to_top"] is True
