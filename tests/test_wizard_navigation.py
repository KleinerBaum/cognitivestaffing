"""Tests for the streamlined wizard navigation router.

The router binds ``wizard.metadata`` at import time, so both modules are patched
in lockstep to keep dependency expectations realistic.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, MutableMapping, Sequence
from types import ModuleType
from typing import Any, Dict, List, Mapping

# ``wizard.flow`` imports ``sidebar.salary`` which in turn pulls ``wizard``
# into the sidebar package, so stub the module hierarchy to avoid circular
# import churn during router unit tests.
import sys

if "sidebar" not in sys.modules:
    sidebar_stub = ModuleType("sidebar")
    sidebar_stub.__path__ = []  # mark as a package for import machinery
    sys.modules["sidebar"] = sidebar_stub

salary_stub = ModuleType("sidebar.salary")


def _format_salary_range_stub(*_args: object, **_kwargs: object) -> str:
    return ""


def _resolve_sidebar_benefits_stub(*_args: object, **_kwargs: object) -> dict[str, Any]:
    return {"entries": []}


salary_stub.format_salary_range = _format_salary_range_stub
salary_stub.resolve_sidebar_benefits = _resolve_sidebar_benefits_stub
sys.modules["sidebar.salary"] = salary_stub

import pytest
import streamlit as st

import wizard.metadata as wizard_metadata
import wizard_router as wizard_router_module
from constants.keys import StateKeys
from pages.base import WizardPage
from wizard_router import StepRenderer, WizardContext, WizardRouter

# ``WizardRouter`` reuses the shared metadata module, so tests patch both
# namespaces when faking critical-field gaps.


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


class _QueryParamStore(MutableMapping[str, List[str]]):
    """In-memory stand-in for Streamlit's query param proxy."""

    def __init__(self) -> None:
        self._data: Dict[str, List[str]] = {}

    def __getitem__(self, key: str) -> List[str]:
        return self._data[key]

    def __setitem__(self, key: str, value: object) -> None:
        if isinstance(value, str):
            normalized = [value]
        elif isinstance(value, Sequence):
            normalized = [str(item) for item in value]
        else:
            normalized = [str(value)]
        self._data[key] = normalized

    def __delitem__(self, key: str) -> None:
        del self._data[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def clear(self) -> None:  # pragma: no cover - passthrough to dict.clear
        self._data.clear()

    def get_all(self, key: str) -> List[str]:
        return list(self._data.get(key, []))


@pytest.fixture()
def query_params(monkeypatch: pytest.MonkeyPatch) -> _QueryParamStore:
    """Provide an isolated query-param store for navigation tests."""

    store = _QueryParamStore()
    monkeypatch.setattr(st, "query_params", store, raising=False)
    return store


_STEP_DEFINITIONS: tuple[tuple[str, int, bool, tuple[str, ...]], ...] = (
    ("jobad", 0, False, ()),
    ("company", 1, False, ("company.name",)),
    ("team", 2, False, ()),
    ("role_tasks", 3, False, ()),
    ("skills", 4, False, ()),
    ("benefits", 5, True, ()),
    ("interview", 6, False, ()),
    ("summary", 7, False, ()),
)


def _build_pages() -> tuple[WizardPage, ...]:
    pages: list[WizardPage] = []
    for key, _legacy_index, allow_skip, required_fields in _STEP_DEFINITIONS:
        title = key.replace("_", " ").title()
        pages.append(
            WizardPage(
                key=key,
                label=(title, title),
                panel_header=(title, title),
                panel_subheader=(title, title),
                panel_intro_variants=((f"Intro {title}", f"Intro {title}"),),
                required_fields=required_fields,
                summary_fields=(),
                allow_skip=allow_skip,
            )
        )
    return tuple(pages)


def _build_renderers(log: List[str]) -> Dict[str, StepRenderer]:
    renderers: Dict[str, StepRenderer] = {}
    for key, legacy_index, _allow_skip, _required_fields in _STEP_DEFINITIONS:

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

    monkeypatch.setattr(wizard_metadata, "get_missing_critical_fields", fake_missing)
    monkeypatch.setattr(wizard_router_module, "get_missing_critical_fields", fake_missing)

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


def test_progress_zero_required_fields_waits_for_completion(
    monkeypatch: pytest.MonkeyPatch,
    query_params: Dict[str, List[str]],
) -> None:
    """Pages without required fields should remain at 0% until completed."""

    missing_ref = {"value": []}

    def fake_missing() -> List[str]:
        return list(missing_ref["value"])

    monkeypatch.setattr(wizard_metadata, "get_missing_critical_fields", fake_missing)
    monkeypatch.setattr(wizard_router_module, "get_missing_critical_fields", fake_missing)

    jobad_page = WizardPage(
        key="jobad",
        label=("Jobad", "Jobad"),
        panel_header=("Header", "Header"),
        panel_subheader=("Sub", "Sub"),
        panel_intro_variants=(("Intro", "Intro"),),
        required_fields=(),
        summary_fields=(),
        allow_skip=False,
    )
    pages = (jobad_page,)
    renderers = {
        jobad_page.key: StepRenderer(
            callback=lambda _context: None,
            legacy_index=0,
        )
    }
    context = WizardContext(schema={}, critical_fields=[])

    def resolver(_data: Mapping[str, Any], _path: str, default: Any | None) -> Any | None:
        return default

    router = WizardRouter(
        pages=pages,
        renderers=renderers,
        context=context,
        value_resolver=resolver,
    )

    snapshots = router._build_progress_snapshots()
    assert snapshots
    assert snapshots[0].completion_ratio == 0.0

    router._state["completed_steps"] = [jobad_page.key]
    snapshots = router._build_progress_snapshots()
    assert snapshots[0].completion_ratio == 1.0


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
    assert "jobad" in completed
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
    assert wizard_state["current_step"] == "interview"
    assert query_params["step"] == ["interview"]
    assert "benefits" in wizard_state.get("completed_steps", [])
    assert "benefits" in wizard_state.get("skipped_steps", [])
    assert st.session_state["_wizard_scroll_to_top"] is True


def test_company_step_disables_next_until_required_answer(
    monkeypatch: pytest.MonkeyPatch, query_params: Dict[str, List[str]]
) -> None:
    """Missing required fields (often surfaced via follow-ups) should block Next."""

    st.session_state[StateKeys.PROFILE] = {"company": {}, "meta": {}}
    st.session_state[StateKeys.FOLLOWUPS] = [{"field": "company.name", "question": "?", "priority": "critical"}]

    missing_ref = {"value": []}
    router, _ = _make_router(monkeypatch, query_params, missing_ref)
    router._state["current_step"] = "company"
    query_params["step"] = ["company"]

    columns = [DummyColumn(), DummyColumn(), DummyColumn()]
    monkeypatch.setattr(st, "columns", lambda *_, **__: columns)
    monkeypatch.setattr(st, "container", lambda: DummyContainer())
    monkeypatch.setattr(st, "markdown", lambda *_, **__: None)
    monkeypatch.setattr(st, "caption", lambda *_, **__: None)
    monkeypatch.setattr(st, "warning", lambda *_, **__: None)
    monkeypatch.setattr(st, "rerun", lambda: (_ for _ in ()).throw(AssertionError("rerun not expected")))

    button_calls: list[dict[str, Any]] = []

    def fake_button(*args: object, **kwargs: object) -> bool:
        button_calls.append({"args": args, "kwargs": kwargs})
        return False

    monkeypatch.setattr(st, "button", fake_button)

    router.run()

    next_calls = [call for call in button_calls if call["kwargs"].get("key") == "wizard_next_company"]
    assert next_calls, "expected Next button to render"
    assert next_calls[-1]["kwargs"].get("disabled", False) is True


def test_company_step_enables_next_after_required_answer(
    monkeypatch: pytest.MonkeyPatch, query_params: Dict[str, List[str]]
) -> None:
    """Providing the missing value should unlock navigation to the next section."""

    st.session_state[StateKeys.PROFILE] = {"company": {"name": "ACME"}, "meta": {}}
    st.session_state[StateKeys.FOLLOWUPS] = [{"field": "company.name", "question": "?", "priority": "critical"}]
    st.session_state["company.name"] = "ACME"

    missing_ref = {"value": []}
    router, _ = _make_router(monkeypatch, query_params, missing_ref)
    router._state["current_step"] = "company"
    query_params["step"] = ["company"]

    columns = [DummyColumn(), DummyColumn(), DummyColumn()]
    monkeypatch.setattr(st, "columns", lambda *_, **__: columns)
    monkeypatch.setattr(st, "container", lambda: DummyContainer())
    monkeypatch.setattr(st, "markdown", lambda *_, **__: None)
    monkeypatch.setattr(st, "caption", lambda *_, **__: None)
    monkeypatch.setattr(st, "warning", lambda *_, **__: None)

    class RerunTriggered(Exception):
        pass

    button_calls: list[dict[str, Any]] = []

    def fake_button(*args: object, **kwargs: object) -> bool:
        button_calls.append({"args": args, "kwargs": kwargs})
        if kwargs.get("key") == "wizard_next_company":
            return True
        return False

    monkeypatch.setattr(st, "button", fake_button)
    monkeypatch.setattr(st, "rerun", lambda: (_ for _ in ()).throw(RerunTriggered()))

    with pytest.raises(RerunTriggered):
        router.run()

    next_calls = [call for call in button_calls if call["kwargs"].get("key") == "wizard_next_company"]
    assert next_calls, "expected Next button to render"
    assert next_calls[-1]["kwargs"].get("disabled", False) is False
    wizard_state = st.session_state["wizard"]
    assert wizard_state["current_step"] == "team"


def test_critical_followup_blocks_until_answered(
    monkeypatch: pytest.MonkeyPatch, query_params: Dict[str, List[str]]
) -> None:
    """Critical follow-ups scoped to the page should gate the Next button."""

    st.session_state[StateKeys.PROFILE] = {"position": {}, "meta": {}}
    st.session_state[StateKeys.FOLLOWUPS] = [{"field": "position.team_size", "priority": "critical"}]

    missing_ref = {"value": []}
    router, _ = _make_router(monkeypatch, query_params, missing_ref)
    router._state["current_step"] = "team"
    query_params["step"] = ["team"]

    columns = [DummyColumn(), DummyColumn(), DummyColumn()]
    monkeypatch.setattr(st, "columns", lambda *_, **__: columns)
    monkeypatch.setattr(st, "container", lambda: DummyContainer())
    monkeypatch.setattr(st, "markdown", lambda *_, **__: None)
    monkeypatch.setattr(st, "caption", lambda *_, **__: None)
    monkeypatch.setattr(st, "warning", lambda *_, **__: None)

    class RerunTriggered(Exception):
        pass

    button_calls: list[dict[str, Any]] = []
    responses = {"wizard_next_team": iter([False, True])}

    def fake_button(*args: object, **kwargs: object) -> bool:
        button_calls.append({"args": args, "kwargs": kwargs})
        key = kwargs.get("key")
        sequence = responses.get(key)
        if sequence is None:
            return False
        try:
            return next(sequence)
        except StopIteration:
            return False

    monkeypatch.setattr(st, "button", fake_button)
    monkeypatch.setattr(st, "rerun", lambda: (_ for _ in ()).throw(RerunTriggered()))

    router.run()

    next_calls = [call for call in button_calls if call["kwargs"].get("key") == "wizard_next_team"]
    assert next_calls, "expected Next button to render"
    assert next_calls[-1]["kwargs"].get("disabled", False) is True

    profile = st.session_state[StateKeys.PROFILE]
    profile.setdefault("position", {})["team_size"] = 5

    with pytest.raises(RerunTriggered):
        router.run()

    next_calls = [call for call in button_calls if call["kwargs"].get("key") == "wizard_next_team"]
    assert next_calls[-1]["kwargs"].get("disabled", False) is False
    wizard_state = st.session_state["wizard"]
    assert wizard_state["current_step"] == "role_tasks"


def test_requirements_followup_blocks_role_tasks(
    monkeypatch: pytest.MonkeyPatch, query_params: Dict[str, List[str]]
) -> None:
    """Critical requirements follow-ups should disable Next until answered."""

    st.session_state[StateKeys.PROFILE] = {"requirements": {}}
    st.session_state[StateKeys.FOLLOWUPS] = [
        {"field": "requirements.background_check_required", "priority": "critical"}
    ]

    missing_ref = {"value": []}
    router, _ = _make_router(monkeypatch, query_params, missing_ref)
    router._state["current_step"] = "role_tasks"
    query_params["step"] = ["role_tasks"]

    columns = [DummyColumn(), DummyColumn(), DummyColumn()]
    monkeypatch.setattr(st, "columns", lambda *_, **__: columns)
    monkeypatch.setattr(st, "container", lambda: DummyContainer())
    monkeypatch.setattr(st, "markdown", lambda *_, **__: None)
    monkeypatch.setattr(st, "caption", lambda *_, **__: None)
    monkeypatch.setattr(st, "warning", lambda *_, **__: None)

    class RerunTriggered(Exception):
        pass

    button_calls: list[dict[str, Any]] = []
    responses = {"wizard_next_role_tasks": iter([False, True])}

    def fake_button(*args: object, **kwargs: object) -> bool:
        button_calls.append({"args": args, "kwargs": kwargs})
        key = kwargs.get("key")
        sequence = responses.get(key)
        if sequence is None:
            return False
        try:
            return next(sequence)
        except StopIteration:
            return False

    monkeypatch.setattr(st, "button", fake_button)
    monkeypatch.setattr(st, "rerun", lambda: (_ for _ in ()).throw(RerunTriggered()))

    router.run()

    next_calls = [call for call in button_calls if call["kwargs"].get("key") == "wizard_next_role_tasks"]
    assert next_calls[-1]["kwargs"].get("disabled", False) is True

    requirements = st.session_state[StateKeys.PROFILE].setdefault("requirements", {})
    requirements["background_check_required"] = True

    with pytest.raises(RerunTriggered):
        router.run()

    next_calls = [call for call in button_calls if call["kwargs"].get("key") == "wizard_next_role_tasks"]
    assert next_calls[-1]["kwargs"].get("disabled", False) is False
    wizard_state = st.session_state["wizard"]
    assert wizard_state["current_step"] == "skills"


def test_summary_followup_counts_as_missing(
    monkeypatch: pytest.MonkeyPatch, query_params: Dict[str, List[str]]
) -> None:
    """Summary follow-ups should be treated as required when critical."""

    st.session_state[StateKeys.PROFILE] = {"summary": {}}
    st.session_state[StateKeys.FOLLOWUPS] = [{"field": "summary.headline", "priority": "critical"}]

    missing_ref = {"value": []}
    router, _ = _make_router(monkeypatch, query_params, missing_ref)
    summary_page = next(page for page in router._pages if page.key == "summary")
    missing = router._missing_required_fields(summary_page)
    assert missing == ["summary.headline"]


def test_optional_followup_does_not_block(monkeypatch: pytest.MonkeyPatch, query_params: Dict[str, List[str]]) -> None:
    """Non-critical follow-ups should not mark the step as incomplete."""

    st.session_state[StateKeys.PROFILE] = {"summary": {}}
    st.session_state[StateKeys.FOLLOWUPS] = [{"field": "summary.headline", "priority": "normal"}]

    missing_ref = {"value": []}
    router, _ = _make_router(monkeypatch, query_params, missing_ref)
    summary_page = next(page for page in router._pages if page.key == "summary")
    missing = router._missing_required_fields(summary_page)
    assert missing == []
