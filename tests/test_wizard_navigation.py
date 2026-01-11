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
from constants.keys import ProfilePaths, StateKeys
from wizard.navigation_types import StepRenderer, WizardContext
from wizard_pages.base import WizardPage
from wizard_router import WizardRouter

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
        if hasattr(st, "button"):
            return st.button(*_args, **_kwargs)
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


class _SessionStateShim(dict):
    """Lightweight dict-based replacement for ``st.session_state`` during tests."""

    def clear(self) -> None:  # pragma: no cover - uses dict.clear
        super().clear()


@pytest.fixture(autouse=True)
def session_state_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch ``st.session_state`` with a deterministic in-memory mapping."""

    state = _SessionStateShim()
    monkeypatch.setattr(st, "session_state", state, raising=False)
    yield
    state.clear()


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
    (
        "company",
        1,
        False,
        ("business_context.domain",),
    ),
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

    original_missing = wizard_metadata.get_missing_critical_fields

    def fake_missing(*args: object, **kwargs: object) -> List[str]:
        if missing_ref["value"] is None:
            return list(original_missing(*args, **kwargs))
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


def test_invalid_query_param_defaults_to_first_step(
    monkeypatch: pytest.MonkeyPatch, query_params: Dict[str, List[str]]
) -> None:
    """Unknown step keys in the query string should not break navigation."""

    st.session_state[StateKeys.PROFILE] = {"meta": {}}
    query_params["step"] = ["EMPLOYMENT_OVERTIME_TOGGLE_HELP"]

    missing_ref = {"value": []}
    router, _ = _make_router(monkeypatch, query_params, missing_ref)

    first_step = _STEP_DEFINITIONS[0][0]
    assert router._state["current_step"] == first_step
    assert query_params["step"] == [first_step]


def test_active_steps_filter_inactive_team(monkeypatch: pytest.MonkeyPatch, query_params: Dict[str, List[str]]) -> None:
    """Steps should be filtered out when their schema sections are missing."""

    st.session_state[StateKeys.PROFILE] = {"meta": {}, "position": {}}
    st.session_state["_schema"] = {"properties": {"company": {}, "position": {}}}

    missing_ref = {"value": []}
    router, _ = _make_router(monkeypatch, query_params, missing_ref)

    active_keys = [page.key for page in router._controller.pages]
    assert "team" not in active_keys


def test_navigation_skips_inactive_steps(monkeypatch: pytest.MonkeyPatch, query_params: Dict[str, List[str]]) -> None:
    """Next/previous navigation should skip inactive steps."""

    st.session_state[StateKeys.PROFILE] = {"meta": {}, "position": {}}
    st.session_state["_schema"] = {"properties": {"company": {}, "position": {}}}

    missing_ref = {"value": []}
    router, _ = _make_router(monkeypatch, query_params, missing_ref)
    router._state["current_step"] = "company"
    query_params["step"] = ["company"]

    next_key = router._controller.next_key(router._page_map["company"])
    assert next_key == "role_tasks"


def test_query_param_inactive_step_redirects(
    monkeypatch: pytest.MonkeyPatch,
    query_params: Dict[str, List[str]],
) -> None:
    """Query params targeting inactive steps should resolve safely."""

    st.session_state[StateKeys.PROFILE] = {"meta": {}, "position": {}}
    st.session_state["_schema"] = {"properties": {"company": {}, "position": {}}}
    query_params["step"] = ["team"]

    missing_ref = {"value": []}
    router, _ = _make_router(monkeypatch, query_params, missing_ref)

    assert router._state["current_step"] == "role_tasks"
    assert query_params["step"] == ["role_tasks"]


def test_progress_zero_required_fields_waits_for_completion(
    monkeypatch: pytest.MonkeyPatch,
    query_params: Dict[str, List[str]],
) -> None:
    """Pages without required fields should remain at 0% until completed."""

    missing_ref = {"value": []}

    original_missing = wizard_metadata.get_missing_critical_fields

    def fake_missing(*args: object, **kwargs: object) -> List[str]:
        if missing_ref["value"] is None:
            return list(original_missing(*args, **kwargs))
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
    missing_ref = {"value": None}
    router, _ = _make_router(monkeypatch, query_params, missing_ref)

    with pytest.raises(RuntimeError):
        router.navigate("company", mark_current_complete=True)

    wizard_state = router._state
    assert wizard_state["current_step"] == "company"
    assert query_params["step"] == ["company"]
    assert st.session_state["_wizard_scroll_to_top"] is True
    completed = wizard_state.get("completed_steps", [])
    assert "jobad" in completed
    assert rerun_called["value"]


def test_next_advances_linearly(monkeypatch: pytest.MonkeyPatch, query_params: Dict[str, List[str]]) -> None:
    """Next should move to the immediate next step without requiring backtracking."""

    st.session_state[StateKeys.PROFILE] = {
        "business_context": {"domain": "FinTech"},
        "company": {
            "name": "ACME",
            "contact_name": "Alex Applicant",
            "contact_email": "contact@example.com",
            "contact_phone": "+49 30 1234567",
        },
        "location": {"primary_city": "Berlin", "country": "DE"},
        "meta": {},
    }
    st.session_state[StateKeys.FOLLOWUPS] = []
    st.session_state[ProfilePaths.COMPANY_CONTACT_EMAIL] = "contact@example.com"
    st.session_state[ProfilePaths.LOCATION_PRIMARY_CITY] = "Berlin"

    missing_ref = {"value": None}
    router, _ = _make_router(monkeypatch, query_params, missing_ref)

    columns = [DummyColumn(), DummyColumn(), DummyColumn()]
    monkeypatch.setattr(st, "columns", lambda *_, **__: columns)
    monkeypatch.setattr(st, "container", lambda: DummyContainer())
    monkeypatch.setattr(st, "markdown", lambda *_, **__: None)
    monkeypatch.setattr(st, "caption", lambda *_, **__: None)
    monkeypatch.setattr(st, "warning", lambda *_, **__: None)

    class RerunTriggered(Exception):
        pass

    responses = {
        "wizard_next_jobad_bottom": iter([True]),
        "wizard_next_company_bottom": iter([True]),
    }

    def fake_button(*args: object, **kwargs: object) -> bool:
        key = kwargs.get("key")
        if key is None:
            return False
        sequence = responses.get(key)
        if sequence is None:
            return False
        try:
            return next(sequence)
        except StopIteration:
            return False

    monkeypatch.setattr(st, "button", fake_button)
    monkeypatch.setattr(st, "rerun", lambda: (_ for _ in ()).throw(RerunTriggered()))

    with pytest.raises(RerunTriggered):
        router.run()

    assert router._state["current_step"] == "company"
    assert query_params["step"] == ["company"]

    with pytest.raises(RerunTriggered):
        router.run()

    assert router._state["current_step"] == "team"
    assert query_params["step"] == ["team"]


def test_pending_incomplete_jump_redirects_to_first_incomplete(
    monkeypatch: pytest.MonkeyPatch, query_params: Dict[str, List[str]]
) -> None:
    """Pending incomplete jumps should pick the matching legacy step."""

    st.session_state[StateKeys.PENDING_INCOMPLETE_JUMP] = True
    missing_ref = {"value": ["position.job_title"]}
    router, _ = _make_router(monkeypatch, query_params, missing_ref)

    wizard_state = router._state
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

    missing_ref = {"value": None}
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

    def fake_button(*_args: object, **_kwargs: object) -> bool:
        key = _kwargs.get("key")
        if key == "wizard_next_benefits_bottom":
            return False
        if key == "wizard_skip_benefits_bottom":
            return True
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

    missing_ref = {"value": None}
    router, _ = _make_router(monkeypatch, query_params, missing_ref)
    router._state["current_step"] = "benefits"
    query_params["step"] = ["benefits"]

    with pytest.raises(RerunTriggered):
        router.run()

    wizard_state = router._state
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

    next_calls = [call for call in button_calls if call["kwargs"].get("key") == "wizard_next_company_bottom"]
    assert next_calls, "expected Next button to render"
    assert next_calls[-1]["kwargs"].get("disabled", False) is True


def test_run_handles_renderer_exception_gracefully(
    monkeypatch: pytest.MonkeyPatch,
    query_params: Dict[str, List[str]],
) -> None:
    """Renderer failures should surface inline errors without crashing the app."""

    captured_errors: list[str] = []
    monkeypatch.setattr(st, "markdown", lambda *_, **__: None)
    monkeypatch.setattr(st, "caption", lambda *_, **__: None)
    monkeypatch.setattr(st, "warning", lambda *_, **__: None)
    monkeypatch.setattr(st, "container", lambda: DummyContainer())
    monkeypatch.setattr(st, "columns", lambda *_, **__: [DummyColumn(), DummyColumn(), DummyColumn()])
    monkeypatch.setattr(st, "button", lambda *_, **__: False)
    monkeypatch.setattr(st, "rerun", lambda: (_ for _ in ()).throw(AssertionError("rerun not expected")))
    monkeypatch.setattr(st, "error", lambda message, **__: captured_errors.append(message))
    monkeypatch.setattr(st, "expander", lambda *_, **__: DummyContainer())
    monkeypatch.setattr(st, "exception", lambda *_, **__: None)

    missing_ref = {"value": None}
    router, _ = _make_router(monkeypatch, query_params, missing_ref)

    def _failing_callback(_context: WizardContext) -> None:
        raise ValueError("boom")

    first_key = _STEP_DEFINITIONS[0][0]
    router._renderers[first_key] = StepRenderer(callback=_failing_callback, legacy_index=0)

    router.run()

    assert captured_errors, "expected error banner to be displayed"


def test_router_bootstrap_skips_repeated_query_sync(
    monkeypatch: pytest.MonkeyPatch,
    query_params: Dict[str, List[str]],
) -> None:
    """Router should only sync query params once per Streamlit session."""

    call_count = {"value": 0}
    original_sync = WizardRouter._sync_with_query_params

    def _counting_sync(self: WizardRouter) -> None:
        call_count["value"] += 1
        original_sync(self)

    monkeypatch.setattr(WizardRouter, "_sync_with_query_params", _counting_sync)

    missing_ref = {"value": []}
    _make_router(monkeypatch, query_params, missing_ref)
    assert call_count["value"] == 1

    _make_router(monkeypatch, query_params, missing_ref)
    assert call_count["value"] == 1, "bootstrap should skip duplicate syncs"


def test_company_step_enables_next_after_required_answer(
    monkeypatch: pytest.MonkeyPatch, query_params: Dict[str, List[str]]
) -> None:
    """Providing the missing value should unlock navigation to the next section."""

    st.session_state[StateKeys.PROFILE] = {
        "business_context": {"domain": "FinTech"},
        "company": {
            "name": "ACME",
            "contact_name": "Alex Applicant",
            "contact_email": "contact@example.com",
            "contact_phone": "+49 30 1234567",
        },
        "location": {"primary_city": "Berlin", "country": "DE"},
        "meta": {},
    }
    st.session_state[StateKeys.FOLLOWUPS] = [{"field": "company.name", "question": "?", "priority": "critical"}]
    st.session_state["company.name"] = "ACME"
    st.session_state[ProfilePaths.COMPANY_CONTACT_EMAIL] = "contact@example.com"
    st.session_state[ProfilePaths.LOCATION_PRIMARY_CITY] = "Berlin"

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
        if kwargs.get("key") == "wizard_next_company_bottom":
            return True
        return False

    monkeypatch.setattr(st, "button", fake_button)
    monkeypatch.setattr(st, "rerun", lambda: (_ for _ in ()).throw(RerunTriggered()))

    with pytest.raises(RerunTriggered):
        router.run()

    next_calls = [call for call in button_calls if call["kwargs"].get("key") == "wizard_next_company_bottom"]
    assert next_calls, "expected Next button to render"
    assert next_calls[-1]["kwargs"].get("disabled", False) is False
    wizard_state = router._state
    assert wizard_state["current_step"] == "team"


def test_company_step_persists_contact_email_from_widget_state(
    monkeypatch: pytest.MonkeyPatch,
    query_params: Dict[str, List[str]],
) -> None:
    """Contact email should persist from widget state into the profile."""

    st.session_state[StateKeys.PROFILE] = {
        "company": {"name": "ACME", "contact_email": ""},
        "location": {"primary_city": "Berlin"},
        "meta": {},
    }
    st.session_state[ProfilePaths.COMPANY_CONTACT_EMAIL] = "typed@example.com"

    missing_ref = {"value": None}
    router, _ = _make_router(monkeypatch, query_params, missing_ref)
    page = router._page_map["company"]
    missing = router._missing_required_fields(page)
    assert str(ProfilePaths.COMPANY_CONTACT_EMAIL) not in missing
    profile = st.session_state[StateKeys.PROFILE]
    assert profile["company"].get("contact_email") == "typed@example.com"


def test_company_step_persists_primary_city_from_widget_state(
    monkeypatch: pytest.MonkeyPatch,
    query_params: Dict[str, List[str]],
) -> None:
    """Primary city should persist from widget state into the profile."""

    st.session_state[StateKeys.PROFILE] = {
        "company": {"name": "ACME", "contact_email": "contact@example.com"},
        "location": {"primary_city": ""},
        "meta": {},
    }
    st.session_state[ProfilePaths.COMPANY_CONTACT_EMAIL] = "contact@example.com"
    st.session_state[ProfilePaths.LOCATION_PRIMARY_CITY] = "Berlin"

    missing_ref = {"value": None}
    router, _ = _make_router(monkeypatch, query_params, missing_ref)
    page = router._page_map["company"]
    missing = router._missing_required_fields(page)
    assert str(ProfilePaths.LOCATION_PRIMARY_CITY) not in missing
    profile = st.session_state[StateKeys.PROFILE]
    assert profile["location"].get("primary_city") == "Berlin"


def test_company_step_revalidates_contact_email_when_widget_cleared(
    monkeypatch: pytest.MonkeyPatch,
    query_params: Dict[str, List[str]],
) -> None:
    """Clearing the widget should trigger validators even if the profile still has data."""

    st.session_state[StateKeys.PROFILE] = {
        "business_context": {"domain": "FinTech"},
        "company": {"name": "ACME", "contact_email": "contact@example.com"},
        "location": {"primary_city": "Berlin"},
        "meta": {},
    }
    st.session_state[ProfilePaths.COMPANY_CONTACT_EMAIL] = ""
    st.session_state[ProfilePaths.LOCATION_PRIMARY_CITY] = "Berlin"

    missing_ref = {"value": None}
    router, _ = _make_router(monkeypatch, query_params, missing_ref)
    page = router._page_map["company"]
    missing = router._missing_required_fields(page)

    assert str(ProfilePaths.COMPANY_CONTACT_EMAIL) in missing
    profile = st.session_state[StateKeys.PROFILE]
    assert not profile["company"].get("contact_email")


def test_company_step_revalidates_primary_city_when_widget_cleared(
    monkeypatch: pytest.MonkeyPatch,
    query_params: Dict[str, List[str]],
) -> None:
    """Clearing the primary city widget should blank the profile and gate navigation."""

    st.session_state[StateKeys.PROFILE] = {
        "company": {"name": "ACME", "contact_email": "contact@example.com"},
        "location": {"primary_city": "Berlin"},
        "meta": {},
    }
    st.session_state[ProfilePaths.COMPANY_CONTACT_EMAIL] = "contact@example.com"
    st.session_state[ProfilePaths.LOCATION_PRIMARY_CITY] = ""

    missing_ref = {"value": None}
    router, _ = _make_router(monkeypatch, query_params, missing_ref)
    page = router._page_map["company"]
    missing = router._missing_required_fields(page)

    assert str(ProfilePaths.LOCATION_PRIMARY_CITY) in missing
    profile = st.session_state[StateKeys.PROFILE]
    assert not profile["location"].get("primary_city")


def test_company_step_relocks_after_contact_fields_cleared(
    monkeypatch: pytest.MonkeyPatch,
    query_params: Dict[str, List[str]],
) -> None:
    """Navigation should disable itself when validators blank the profile."""

    st.session_state[StateKeys.PROFILE] = {
        "company": {"name": "ACME", "contact_email": "contact@example.com"},
        "location": {"primary_city": "Berlin"},
        "meta": {},
    }
    st.session_state[ProfilePaths.COMPANY_CONTACT_EMAIL] = "contact@example.com"
    st.session_state[ProfilePaths.LOCATION_PRIMARY_CITY] = "Berlin"

    missing_ref = {"value": []}
    router, _ = _make_router(monkeypatch, query_params, missing_ref)
    router._state["current_step"] = "company"
    query_params["step"] = ["company"]

    def _invalidate_contact_fields(_context: WizardContext) -> None:
        profile = st.session_state[StateKeys.PROFILE]
        profile["company"]["contact_email"] = ""
        profile["location"]["primary_city"] = ""

    router._renderers["company"] = StepRenderer(
        callback=_invalidate_contact_fields,
        legacy_index=1,
    )

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

    next_calls = [call for call in button_calls if call["kwargs"].get("key") == "wizard_next_company_bottom"]
    assert next_calls, "expected Next button to render"
    assert next_calls[-1]["kwargs"].get("disabled", False) is True


def test_company_step_surfaces_warning_when_contact_fields_missing(
    monkeypatch: pytest.MonkeyPatch,
    query_params: Dict[str, List[str]],
) -> None:
    """Missing contact email or city should render a bilingual warning near navigation."""

    st.session_state[StateKeys.PROFILE] = {
        "company": {"name": "ACME", "contact_email": ""},
        "location": {"primary_city": ""},
        "meta": {},
    }
    st.session_state[ProfilePaths.COMPANY_CONTACT_EMAIL] = ""
    st.session_state[ProfilePaths.LOCATION_PRIMARY_CITY] = ""

    missing_ref = {"value": None}
    router, _ = _make_router(monkeypatch, query_params, missing_ref)
    router._state["current_step"] = "company"
    query_params["step"] = ["company"]

    columns = [DummyColumn(), DummyColumn(), DummyColumn()]
    monkeypatch.setattr(st, "columns", lambda *_, **__: columns)
    monkeypatch.setattr(st, "container", lambda: DummyContainer())
    monkeypatch.setattr(st, "markdown", lambda *_, **__: None)
    monkeypatch.setattr(st, "caption", lambda *_, **__: None)

    warnings: list[str] = []

    def fake_warning(message: str) -> None:
        warnings.append(message)

    monkeypatch.setattr(st, "warning", fake_warning)

    def fake_button(*_args: object, **kwargs: object) -> bool:
        return kwargs.get("key") == "wizard_next_company_bottom"

    monkeypatch.setattr(st, "button", fake_button)
    monkeypatch.setattr(st, "rerun", lambda: None)

    router.run()

    assert warnings, "expected a warning banner when contact fields are missing"
    assert "Kontakt-E-Mail" in warnings[-1]


def test_company_next_click_stays_blocked_when_contact_fields_missing(
    monkeypatch: pytest.MonkeyPatch,
    query_params: Dict[str, List[str]],
) -> None:
    """Navigation should stay blocked when required validators report errors."""

    st.session_state[StateKeys.PROFILE] = {
        "company": {"name": "ACME", "contact_email": "contact@example.com"},
        "location": {"primary_city": "Berlin"},
        "meta": {},
    }
    st.session_state[ProfilePaths.COMPANY_CONTACT_EMAIL] = "contact@example.com"
    st.session_state[ProfilePaths.LOCATION_PRIMARY_CITY] = "Berlin"

    missing_ref = {"value": None}
    router, _ = _make_router(monkeypatch, query_params, missing_ref)
    router._state["current_step"] = "company"
    query_params["step"] = ["company"]

    call_counter = {"value": 0}

    def _validate_stub(self: WizardRouter, fields: Sequence[str]) -> dict[str, tuple[str, str]]:
        call_counter["value"] += 1
        return {str(ProfilePaths.COMPANY_CONTACT_EMAIL): ("Kontakt fehlt", "Contact missing")}

    monkeypatch.setattr(WizardRouter, "_validate_required_field_inputs", _validate_stub)

    columns = [DummyColumn(), DummyColumn(), DummyColumn()]
    monkeypatch.setattr(st, "columns", lambda *_, **__: columns)
    monkeypatch.setattr(st, "container", lambda: DummyContainer())
    monkeypatch.setattr(st, "markdown", lambda *_, **__: None)
    monkeypatch.setattr(st, "warning", lambda *_, **__: None)
    captions: list[str] = []
    monkeypatch.setattr(st, "caption", lambda message, **__: captions.append(message))

    class RerunTriggered(Exception):
        pass

    monkeypatch.setattr(st, "rerun", lambda: (_ for _ in ()).throw(RerunTriggered()))

    responses = {"wizard_next_company_bottom": iter([True])}

    def fake_button(*_args: object, **kwargs: object) -> bool:
        key = kwargs.get("key")
        sequence = responses.get(key)
        if sequence is None:
            return False
        try:
            return next(sequence)
        except StopIteration:
            return False

    monkeypatch.setattr(st, "button", fake_button)

    router.run()

    assert call_counter["value"] >= 1, "validators should still execute"
    assert router._state["current_step"] == "company"
    assert query_params["step"] == ["company"]


def test_missing_required_fields_hint_renders_under_next_button(
    monkeypatch: pytest.MonkeyPatch,
    query_params: Dict[str, List[str]],
) -> None:
    """Missing required data should surface as a hint beside the Next button."""

    st.session_state[StateKeys.PROFILE] = {
        "company": {"name": "ACME", "contact_email": "contact@example.com"},
        "location": {"primary_city": "Berlin"},
        "meta": {},
    }
    st.session_state["lang"] = "de"

    missing_ref = {"value": []}
    router, _ = _make_router(monkeypatch, query_params, missing_ref)
    router._state["current_step"] = "company"
    query_params["step"] = ["company"]

    st.session_state[str(ProfilePaths.COMPANY_CONTACT_EMAIL)] = ""

    captions: list[str] = []

    class _CapturingColumn(DummyColumn):
        def caption(self, message: str, **_: object) -> None:  # type: ignore[override]
            captions.append(message)

    columns = [_CapturingColumn(), _CapturingColumn(), _CapturingColumn()]
    monkeypatch.setattr(st, "columns", lambda *_, **__: columns)
    monkeypatch.setattr(st, "container", lambda: DummyContainer())
    monkeypatch.setattr(st, "markdown", lambda *_, **__: None)
    monkeypatch.setattr(st, "button", lambda *_, **__: False)
    monkeypatch.setattr(st, "warning", lambda *_, **__: None)

    router.run()

    assert any("Pflicht" in entry or "required" in entry.lower() for entry in captions)


def test_company_required_validators_use_profile_when_widget_state_missing(
    monkeypatch: pytest.MonkeyPatch,
    query_params: Dict[str, List[str]],
) -> None:
    """Validators should reuse profile data when widget state is unavailable."""

    st.session_state[StateKeys.PROFILE] = {
        "company": {"name": "ACME", "contact_email": "contact@example.com"},
        "location": {"primary_city": "Berlin"},
        "meta": {},
    }
    st.session_state.pop(ProfilePaths.COMPANY_CONTACT_EMAIL, None)
    st.session_state.pop(ProfilePaths.LOCATION_PRIMARY_CITY, None)

    missing_ref = {"value": []}
    router, _ = _make_router(monkeypatch, query_params, missing_ref)
    page = router._page_map["company"]
    missing = router._missing_required_fields(page)

    assert str(ProfilePaths.COMPANY_CONTACT_EMAIL) not in missing
    assert str(ProfilePaths.LOCATION_PRIMARY_CITY) not in missing


def test_critical_followup_blocks_until_answered(
    monkeypatch: pytest.MonkeyPatch, query_params: Dict[str, List[str]]
) -> None:
    """Critical follow-ups scoped to the page should gate the Next button."""

    st.session_state[StateKeys.PROFILE] = {"position": {}, "meta": {}}
    st.session_state[StateKeys.FOLLOWUPS] = [{"field": "team.reporting_line", "priority": "critical"}]

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
    responses = {"wizard_next_team_bottom": iter([False, True])}

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

    next_calls = [call for call in button_calls if call["kwargs"].get("key") == "wizard_next_team_bottom"]
    assert next_calls, "expected Next button to render"
    assert next_calls[-1]["kwargs"].get("disabled", False) is True

    profile = st.session_state[StateKeys.PROFILE]
    profile.setdefault("team", {})["reporting_line"] = "Engineering"

    with pytest.raises(RerunTriggered):
        router.run()

    next_calls = [call for call in button_calls if call["kwargs"].get("key") == "wizard_next_team_bottom"]
    assert next_calls[-1]["kwargs"].get("disabled", False) is False
    wizard_state = router._state
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
    responses = {"wizard_next_role_tasks_bottom": iter([False, True])}

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

    next_calls = [call for call in button_calls if call["kwargs"].get("key") == "wizard_next_role_tasks_bottom"]
    assert next_calls[-1]["kwargs"].get("disabled", False) is True

    requirements = st.session_state[StateKeys.PROFILE].setdefault("requirements", {})
    requirements["background_check_required"] = True

    with pytest.raises(RerunTriggered):
        router.run()

    next_calls = [call for call in button_calls if call["kwargs"].get("key") == "wizard_next_role_tasks_bottom"]
    assert next_calls[-1]["kwargs"].get("disabled", False) is False
    wizard_state = router._state
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
