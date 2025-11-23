from __future__ import annotations

from datetime import date
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
