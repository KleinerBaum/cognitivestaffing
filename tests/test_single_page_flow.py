from __future__ import annotations

from collections.abc import Callable, Sequence
import pytest
import streamlit as st

from constants.flow_mode import FlowMode
from constants.keys import StateKeys
import wizard.flow as wizard_flow
from wizard.navigation_types import StepRenderer, WizardContext
from wizard.step_registry import step_keys


class DummyContainer:
    """Minimal context manager stub for Streamlit containers and expanders."""

    def __enter__(self) -> "DummyContainer":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:  # type: ignore[override]
        return False


class _SessionStateShim(dict):
    """Lightweight dict-based replacement for ``st.session_state`` in tests."""

    def clear(self) -> None:  # pragma: no cover - uses dict.clear
        super().clear()


@pytest.fixture(autouse=True)
def stub_streamlit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch Streamlit UI calls to no-ops for flow tests."""

    state = _SessionStateShim()
    monkeypatch.setattr(st, "session_state", state, raising=False)
    monkeypatch.setattr(st, "expander", lambda *_args, **_kwargs: DummyContainer())
    monkeypatch.setattr(st, "container", lambda *_args, **_kwargs: DummyContainer())
    monkeypatch.setattr(st, "markdown", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(st, "caption", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(st, "success", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(st, "warning", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(st, "info", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(st, "divider", lambda *_args, **_kwargs: None)
    yield
    state.clear()


def _build_renderers(log: list[str]) -> dict[str, StepRenderer]:
    renderers: dict[str, StepRenderer] = {}
    for index, key in enumerate(step_keys()):

        def _make_callback(step_key: str) -> Callable[[WizardContext], None]:
            def _callback(_context: WizardContext) -> None:
                log.append(step_key)

            return _callback

        renderers[key] = StepRenderer(callback=_make_callback(key), legacy_index=index)
    return renderers


def test_single_page_renders_all_steps_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """Single-page mode renders every step exactly once per run."""

    st.session_state[StateKeys.FLOW_MODE] = FlowMode.SINGLE_PAGE
    st.session_state[StateKeys.PROFILE] = {}
    render_log: list[str] = []
    renderers = _build_renderers(render_log)
    monkeypatch.setattr(wizard_flow, "STEP_RENDERERS", renderers)

    wizard_flow._run_wizard_v2(schema={}, critical=())

    assert render_log == list(step_keys())


def test_multi_step_renders_current_step_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """Multi-step mode still renders only the active step."""

    st.session_state[StateKeys.FLOW_MODE] = FlowMode.MULTI_STEP
    st.session_state[StateKeys.PROFILE] = {}
    current_step = step_keys()[2]
    st.session_state["wizard"] = {"current_step": current_step}
    render_log: list[str] = []
    renderers = _build_renderers(render_log)
    monkeypatch.setattr(wizard_flow, "STEP_RENDERERS", renderers)

    class FakeRouter:
        def __init__(
            self,
            *,
            pages: Sequence[object],
            renderers: dict[str, StepRenderer],
            context: WizardContext,
            value_resolver: Callable[[dict[str, object], str, object | None], object | None],
        ) -> None:
            self._renderers = renderers
            self._context = context

        def run(self) -> None:
            wizard_state = st.session_state.get("wizard", {}) or {}
            current = wizard_state.get("current_step", next(iter(self._renderers)))
            self._renderers[current].callback(self._context)

    monkeypatch.setattr(wizard_flow, "WizardRouter", FakeRouter)

    wizard_flow._run_wizard_v2(schema={}, critical=())

    assert render_log == [current_step]
