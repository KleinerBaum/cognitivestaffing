from __future__ import annotations

import base64
from types import SimpleNamespace

import streamlit as st

from constants.keys import StateKeys
from sidebar import _collect_branding_display, _store_branding_asset


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
