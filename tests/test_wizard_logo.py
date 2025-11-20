from __future__ import annotations

import pytest
import streamlit as st

from constants.keys import StateKeys
from wizard import _get_company_logo_bytes, _set_company_logo, _summary_company


def test_set_company_logo_updates_single_key() -> None:
    st.session_state.clear()

    _set_company_logo(b"logo-bytes")

    assert st.session_state[StateKeys.JOB_AD_LOGO_DATA] == b"logo-bytes"
    assert "company_logo" not in st.session_state

    _set_company_logo(None)

    assert st.session_state[StateKeys.JOB_AD_LOGO_DATA] is None
    assert "company_logo" not in st.session_state


def test_get_company_logo_bytes_backfills_legacy_key() -> None:
    st.session_state.clear()
    st.session_state["company_logo"] = b"legacy"

    logo = _get_company_logo_bytes()

    assert logo == b"legacy"
    assert st.session_state[StateKeys.JOB_AD_LOGO_DATA] == b"legacy"
    assert "company_logo" not in st.session_state


def test_summary_company_uses_shared_logo(monkeypatch: pytest.MonkeyPatch) -> None:
    st.session_state.clear()
    st.session_state[StateKeys.PROFILE] = {
        "company": {
            "name": "",
            "industry": "",
            "hq_location": "",
            "size": "",
            "website": "",
            "mission": "",
            "culture": "",
            "brand_keywords": "",
        },
        "position": {},
        "requirements": {},
        "location": {},
    }

    _set_company_logo(b"preview")

    monkeypatch.setattr(st, "subheader", lambda *_, **__: None)
    monkeypatch.setattr(st, "caption", lambda *_, **__: None)
    monkeypatch.setattr(st, "text_input", lambda *_, value="", **__: value)
    monkeypatch.setattr(st, "text_area", lambda *_, value="", **__: value)

    class DummyColumn:
        def text_input(self, _label: str, *, value: str = "", **_kwargs: object) -> str:
            return value

        def text_area(self, _label: str, *, value: str = "", **_kwargs: object) -> str:
            return value

    def fake_columns(spec, *_, **__):
        if isinstance(spec, int):
            count = spec
        elif isinstance(spec, (list, tuple)):
            count = len(spec)
        else:
            count = 2
        return [DummyColumn() for _ in range(max(count, 1))]

    monkeypatch.setattr(st, "columns", fake_columns)
    monkeypatch.setattr("wizard._field_lock_config", lambda *args, **kwargs: {"label": args[1]})
    monkeypatch.setattr("wizard._apply_field_lock_kwargs", lambda config, base=None: dict(base or {}))

    captured: dict[str, bytes] = {}

    def fake_image(data: bytes, **_: object) -> None:
        captured["image"] = data

    monkeypatch.setattr(st, "image", fake_image)

    _summary_company()

    assert captured["image"] == b"preview"
    assert st.session_state[StateKeys.JOB_AD_LOGO_DATA] == b"preview"
    assert "company_logo" not in st.session_state
