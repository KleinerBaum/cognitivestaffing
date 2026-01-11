"""Safety net tests for the wizard job ad flow."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Callable, Sequence

import pytest

from constants.keys import StateKeys, UIKeys
from wizard.steps import jobad_step
from wizard_router import WizardContext


class DummyColumn:
    """Lightweight placeholder for Streamlit column context managers."""

    def __enter__(self) -> "DummyColumn":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:  # type: ignore[override]
        return False


class DummyExpander(DummyColumn):
    """Expander stub behaving like a basic context manager."""

    pass


class DummyContainer(DummyColumn):
    """Container stub behaving like a basic context manager."""

    pass


class DummyStreamlit:
    """Minimal Streamlit stub for running wizard steps in tests."""

    def __init__(self) -> None:
        self.session_state: dict[str, object] = {}

    def markdown(self, *_: Any, **__: Any) -> None:
        """Accept markdown calls without rendering."""

    def caption(self, *_: Any, **__: Any) -> None:
        """Accept caption calls without rendering."""

    def info(self, *_: Any, **__: Any) -> None:
        """Accept info calls without rendering."""

    def divider(self, *_: Any, **__: Any) -> None:
        return None

    def error(self, *_: Any, **__: Any) -> None:
        return None

    def columns(self, spec: int | Sequence[object], **__: Any) -> tuple[DummyColumn, ...]:
        _ = spec
        return tuple(DummyColumn() for _ in range(3))

    def container(self, *_: Any, **__: Any) -> DummyContainer:
        return DummyContainer()

    def expander(self, *_: Any, **__: Any) -> DummyExpander:
        return DummyExpander()

    def radio(
        self,
        _label: str,
        *,
        options: Sequence[str],
        index: int = 0,
        key: str | None = None,
        format_func: Callable[[str], str] | None = None,
        **__: Any,
    ) -> str:
        value = options[index] if 0 <= index < len(options) else options[0]
        if format_func:
            format_func(value)
        if key is not None:
            self.session_state[key] = value
        return value

    def checkbox(
        self,
        _label: str,
        *,
        value: bool = False,
        key: str | None = None,
        **__: Any,
    ) -> bool:
        if key is not None:
            self.session_state[key] = value
        return value

    def button(self, *_: Any, **__: Any) -> bool:
        return False

    def text_input(self, label: str, *, key: str | None = None, **__: Any) -> str:
        if key is not None:
            self.session_state[key] = ""
        return ""

    def file_uploader(self, *_: Any, **__: Any) -> None:
        return None

    def __getattr__(self, name: str) -> Callable[..., None]:
        return lambda *args, **kwargs: None


@pytest.fixture()
def stubbed_streamlit(monkeypatch: pytest.MonkeyPatch) -> DummyStreamlit:
    """Provide a stubbed Streamlit module patched into the wizard flow."""

    dummy_st = DummyStreamlit()
    monkeypatch.setattr(jobad_step, "st", dummy_st)
    return dummy_st


@pytest.fixture(autouse=True)
def stub_onboarding_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    """Neutralise expensive onboarding dependencies for fast tests."""

    stub_flow = SimpleNamespace(
        _render_onboarding_hero=lambda: None,
        _maybe_run_extraction=lambda schema: None,
        _render_extraction_review=lambda: False,
        _render_followups_for_step=lambda *args, **kwargs: None,
        _advance_from_onboarding=lambda: None,
        _apply_parsing_mode=lambda mode: mode,
        _queue_extraction_rerun=lambda: None,
        _is_onboarding_locked=lambda: False,
        on_url_changed=lambda: None,
        on_file_uploaded=lambda: None,
        _build_profile_context=lambda profile: {},
        _format_dynamic_message=lambda default, context, variants: default[0],
        _get_profile_state=lambda: {},
    )
    monkeypatch.setattr(jobad_step, "_get_flow_module", lambda: stub_flow)


def test_jobad_step_populates_session_state(stubbed_streamlit: DummyStreamlit) -> None:
    """Calling the job ad step should populate the expected session state keys."""

    stubbed_streamlit.session_state[StateKeys.PROFILE] = {}
    context = WizardContext(schema={}, critical_fields=())

    jobad_step.step_jobad(context)

    assert StateKeys.PROFILE in stubbed_streamlit.session_state
    assert UIKeys.EXTRACTION_REASONING_MODE in stubbed_streamlit.session_state
    assert StateKeys.EXTRACTION_STRICT_FORMAT in stubbed_streamlit.session_state
    assert UIKeys.EXTRACTION_STRICT_FORMAT in stubbed_streamlit.session_state
