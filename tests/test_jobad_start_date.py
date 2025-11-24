from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from typing import Any

import pytest
import streamlit as st

from constants.keys import ProfilePaths
from wizard import flow


class _FakeColumn:
    """Minimal Streamlit column stub for date input rendering."""

    def __init__(self) -> None:
        self.captured: dict[str, Any] = {}

    def container(self) -> "_FakeColumn":  # pragma: no cover - context passthrough
        return self

    def __enter__(self) -> "_FakeColumn":  # pragma: no cover - context protocol
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # pragma: no cover - context protocol
        return None

    def date_input(self, label: str, *, value: Any = None, **kwargs: Any) -> Any:
        self.captured["label"] = label
        self.captured["value"] = value
        self.captured.update(kwargs)
        return value


def test_target_start_date_string_coerced_to_date(monkeypatch: pytest.MonkeyPatch) -> None:
    meta = {"target_start_date": "2025-12-31"}
    widget_key = str(ProfilePaths.META_TARGET_START_DATE)
    st.session_state.clear()
    st.session_state[widget_key] = meta["target_start_date"]

    fake_column = _FakeColumn()
    monkeypatch.setattr(flow, "tr", lambda de, en: en)

    rendered_value = flow._render_target_start_date_input(fake_column, meta)

    assert isinstance(fake_column.captured["value"], date)
    assert fake_column.captured["value"] == date(2025, 12, 31)
    assert st.session_state[widget_key] == date(2025, 12, 31)
    assert rendered_value == date(2025, 12, 31)


class _StubColumn:
    """Minimal column stub capturing date input values."""

    def __init__(self, registry: dict[str, Any]) -> None:
        self.registry = registry

    def container(self) -> "_StubColumn":
        return self

    def __enter__(self) -> "_StubColumn":  # pragma: no cover - context protocol
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # pragma: no cover - context protocol
        return None

    def text_input(self, *_: Any, value: str | None = None, **__: Any) -> str:
        return value or ""

    def number_input(self, *_: Any, value: int | float | None = None, **__: Any) -> int:
        return int(value or 0)

    def date_input(self, *_: Any, value: Any = None, **__: Any) -> Any:
        self.registry.setdefault("dates", []).append(value)
        return value


class _StubStreamlit:
    """Stub Streamlit module for rendering review tabs."""

    def __init__(self) -> None:
        self.session_state: dict[str, Any] = {}
        self.registry: dict[str, Any] = {}

    def markdown(self, *_: Any, **__: Any) -> None:
        return None

    def container(self) -> _StubColumn:
        return _StubColumn(self.registry)

    def columns(self, spec: Any, **__: Any) -> tuple[_StubColumn, ...]:
        count = len(spec) if not isinstance(spec, int) else int(spec)
        return tuple(_StubColumn(self.registry) for _ in range(count))

    def text_area(self, *_: Any, value: str | None = None, **__: Any) -> str:
        return value or ""


def _stub_text_input(
    _: str, __: str, *, widget_factory: Any | None = None, default: Any | None = None, **___: Any
) -> str:
    factory = widget_factory or (lambda *args, **kwargs: default or "")
    return factory("", value=default or "", key=None)


def test_render_review_role_tab_accepts_string_date(monkeypatch: pytest.MonkeyPatch) -> None:
    profile: dict[str, Any] = {
        "position": {},
        "department": {},
        "team": {},
        "meta": {"target_start_date": "2025-12-31"},
    }

    stub_streamlit = _StubStreamlit()
    monkeypatch.setattr(flow, "st", stub_streamlit)
    monkeypatch.setattr(flow, "tr", lambda de, en: en)
    monkeypatch.setattr(flow, "widget_factory", SimpleNamespace(text_input=_stub_text_input))
    monkeypatch.setattr(flow, "_render_inline_followups", lambda *args, **kwargs: None)
    monkeypatch.setattr(flow, "_update_profile", lambda *args, **kwargs: None)
    monkeypatch.setattr(flow, "_coerce_followup_number", lambda value: int(value or 0))

    flow._render_review_role_tab(profile)

    captured_dates = stub_streamlit.registry.get("dates", [])
    assert captured_dates
    assert captured_dates[0] == date(2025, 12, 31)
    assert profile["meta"]["target_start_date"] == "2025-12-31"
