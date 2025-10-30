from __future__ import annotations

import base64
from types import SimpleNamespace

import pytest

import streamlit as st

from constants.keys import ProfilePaths, StateKeys
from models.need_analysis import NeedAnalysisProfile
from pydantic import HttpUrl
from sidebar import _collect_branding_display, _render_branding_overrides, _store_branding_asset


def test_store_branding_asset_updates_state() -> None:
    st.session_state.clear()
    upload = SimpleNamespace(
        name="custom.png",
        type="image/png",
        getvalue=lambda: b"binary-data",
    )

    _store_branding_asset(upload)  # type: ignore[arg-type]

    asset = st.session_state.get(StateKeys.COMPANY_BRANDING_ASSET)
    assert isinstance(asset, dict)
    assert asset["name"] == "custom.png"
    assert asset["type"] == "image/png"
    assert asset["data"] == b"binary-data"


def test_collect_branding_display_prefers_uploaded_asset() -> None:
    st.session_state.clear()
    st.session_state[StateKeys.PROFILE] = {
        "company": {"name": "ACME", "brand_color": "#112233", "logo_url": "https://example.com/logo.svg"}
    }
    st.session_state[StateKeys.COMPANY_INFO_CACHE] = {}
    image_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAASsJTYQAAAAASUVORK5CYII="
    )
    st.session_state[StateKeys.COMPANY_BRANDING_ASSET] = {
        "name": "upload.png",
        "type": "image/png",
        "data": image_bytes,
    }

    display = _collect_branding_display()

    assert display is not None
    assert display.company_name == "ACME"
    assert display.brand_color == "#112233"
    assert isinstance(display.logo_src, str) and display.logo_src.startswith("data:image/png;base64,")


def test_render_branding_overrides_normalizes_httpurl(monkeypatch: pytest.MonkeyPatch) -> None:
    st.session_state.clear()
    profile = NeedAnalysisProfile(company={"logo_url": "https://example.com/logo.svg"})
    st.session_state[StateKeys.PROFILE] = profile.model_dump()
    http_logo = profile.company.logo_url
    assert isinstance(http_logo, HttpUrl)

    st.session_state[ProfilePaths.COMPANY_LOGO_URL.value] = http_logo

    def fake_caption(*_: object, **__: object) -> None:
        return None

    def fake_color_picker(*_: object, key: object | None = None, value: object | None = None, **__: object) -> str:
        result = "" if value is None else (value if isinstance(value, str) else str(value))
        if isinstance(key, str):
            st.session_state[key] = result
        return result

    def fake_text_input(*_: object, key: object | None = None, value: object | None = None, **__: object) -> str:
        if isinstance(key, str) and key in st.session_state:
            assert isinstance(st.session_state[key], str)
        result = "" if value is None else (value if isinstance(value, str) else str(value))
        if isinstance(key, str):
            st.session_state[key] = result
        return result

    monkeypatch.setattr(st, "caption", fake_caption)
    monkeypatch.setattr(st, "color_picker", fake_color_picker)
    monkeypatch.setattr(st, "text_input", fake_text_input)
    monkeypatch.setattr(st, "file_uploader", lambda *_, **__: None)
    monkeypatch.setattr(st, "button", lambda *_, **__: False)
    monkeypatch.setattr(st, "image", lambda *_, **__: None)
    monkeypatch.setattr(st, "rerun", lambda: None)

    class FakeLogic:
        def get_value(self, key: str) -> object | None:
            if key == ProfilePaths.COMPANY_LOGO_URL.value:
                return http_logo
            return st.session_state.get(key)

    monkeypatch.setattr("sidebar._wizard_logic", lambda: FakeLogic())

    _render_branding_overrides()

    stored_logo = st.session_state[ProfilePaths.COMPANY_LOGO_URL.value]
    assert isinstance(stored_logo, str)
    assert stored_logo == str(http_logo)
