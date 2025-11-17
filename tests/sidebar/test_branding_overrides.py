from __future__ import annotations

import base64
from types import SimpleNamespace

import pytest

import streamlit as st

from constants.keys import ProfilePaths, StateKeys
from models.need_analysis import NeedAnalysisProfile
from pydantic import HttpUrl
import sidebar
from sidebar import (
    BRANDING_SETTINGS_EXPANDED_KEY,
    _collect_branding_display,
    _render_app_branding,
    _render_branding_overrides,
    _store_branding_asset,
)


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

    placeholders: list[str] = []

    def fake_color_picker(*_: object, key: object | None = None, value: object | None = None, **__: object) -> str:
        result = "" if value is None else (value if isinstance(value, str) else str(value))
        if isinstance(key, str):
            st.session_state[key] = result
        return result

    def fake_text_input(
        *_,
        key: object | None = None,
        value: object | None = None,
        placeholder: object | None = None,
        **__: object,
    ) -> str:
        if isinstance(placeholder, str):
            placeholders.append(placeholder)
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

    monkeypatch.setattr(sidebar, "logic", FakeLogic())

    _render_branding_overrides()

    stored_logo = st.session_state[ProfilePaths.COMPANY_LOGO_URL.value]
    assert isinstance(stored_logo, str)
    assert stored_logo == str(http_logo)
    assert all("Einfach. Immer. Da." not in item for item in placeholders)
    assert all("example.com/logo.svg" not in item for item in placeholders)


def test_app_branding_cta_sets_expander_state(monkeypatch: pytest.MonkeyPatch) -> None:
    st.session_state.clear()

    monkeypatch.setattr("sidebar._render_app_version", lambda: None)
    monkeypatch.setattr(st, "image", lambda *_, **__: None)
    monkeypatch.setattr(st, "markdown", lambda *_, **__: None)

    info_messages: list[str] = []

    def fake_info(message: str, *args: object, **kwargs: object) -> None:
        info_messages.append(message)

    monkeypatch.setattr(st, "info", fake_info)

    reruns: list[bool] = []

    def fake_button(label: str, *args: object, **kwargs: object) -> bool:
        assert "Branding" in label
        return True

    def fake_rerun() -> None:
        reruns.append(True)

    monkeypatch.setattr(st, "button", fake_button)
    monkeypatch.setattr(st, "rerun", fake_rerun)

    _render_app_branding(None, None)

    assert st.session_state.get(BRANDING_SETTINGS_EXPANDED_KEY) is True
    assert reruns == [True]
    assert any("Branding" in message for message in info_messages)
