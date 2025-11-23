from __future__ import annotations

from datetime import date

import pytest
import streamlit as st

from constants.keys import StateKeys
from tests.utils import (
    FollowupEntry,
    ProfileDict,
    SessionBootstrap,
    empty_profile,
    make_followup,
)
from wizard import _render_followups_for_section
import wizard.sections.followups as followups


class DummyContainer:
    def __enter__(self) -> "DummyContainer":
        return self

    def __exit__(self, *args: object, **kwargs: object) -> bool:  # noqa: D401 - context manager contract
        return False

    def markdown(self, *args: object, **kwargs: object) -> None:
        return None

    def caption(self, *args: object, **kwargs: object) -> None:
        return None

    def columns(self, *_args: object, **_kwargs: object) -> list[DummyContainer]:
        return []

    def __getattr__(self, _name: str):  # type: ignore[override]
        return lambda *args, **kwargs: None


class FakeLogger:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def exception(self, message: str, *args: object, **_: object) -> None:
        formatted = message % args if args else message
        self.messages.append(formatted)


def _stub_streamlit(monkeypatch: pytest.MonkeyPatch, container: DummyContainer) -> None:
    monkeypatch.setattr(st, "container", lambda: container)
    monkeypatch.setattr(st, "markdown", lambda *a, **k: None)
    monkeypatch.setattr(st, "caption", lambda *a, **k: None)
    monkeypatch.setattr(st, "toast", lambda *a, **k: None)
    monkeypatch.setattr(st, "columns", lambda *a, **k: [])
    monkeypatch.setattr(st, "button", lambda *a, **k: False)
    monkeypatch.setattr(st, "checkbox", lambda *a, **k: False)
    monkeypatch.setattr(st, "text_input", lambda *a, **k: "")
    monkeypatch.setattr(st, "text_area", lambda *a, **k: "")
    monkeypatch.setattr(st, "number_input", lambda *a, **k: 0.0)
    monkeypatch.setattr(st, "date_input", lambda *a, **k: date.today())


def test_followup_render_error_coalesced(monkeypatch: pytest.MonkeyPatch) -> None:
    """Rendering failures should be logged once per step and halt subsequent questions."""

    SessionBootstrap(followups=[make_followup("team.size", "Size?"), make_followup("team.stack", "Stack?")]).apply()
    data: ProfileDict = empty_profile()
    fake_logger = FakeLogger()
    monkeypatch.setattr(followups, "logger", fake_logger)
    container = DummyContainer()
    _stub_streamlit(monkeypatch, container)

    def failing_renderer(q: FollowupEntry, _data: ProfileDict) -> None:
        raise RuntimeError(f"boom: {q['field']}")

    monkeypatch.setattr(followups, "_resolve_followup_renderer", lambda: failing_renderer)

    _render_followups_for_section(["team"], data, exact=False, step_label="Team")

    assert len(fake_logger.messages) == 1
    assert "Team" in fake_logger.messages[0]
    assert "team.size" in fake_logger.messages[0]
    assert st.session_state[StateKeys.FOLLOWUPS]  # follow-ups remain queued after failure
