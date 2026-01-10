from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest
import streamlit as st

from openai_utils import api as openai_api


class _RaisingSessionState(dict):
    def __getitem__(self, key: object) -> object:
        raise AssertionError("Session state accessed from background thread")

    def get(self, key: object, default: object | None = None) -> object | None:
        raise AssertionError("Session state accessed from background thread")

    def __setitem__(self, key: object, value: object) -> None:
        raise AssertionError("Session state accessed from background thread")


def test_streamlit_access_only_on_main_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(st, "session_state", _RaisingSessionState(), raising=False)

    with ThreadPoolExecutor(max_workers=1) as executor:
        assert executor.submit(openai_api._allow_streamlit_access).result() is False
        executor.submit(openai_api._flag_openai_unavailable, "reason").result()
        executor.submit(openai_api._show_missing_api_key_alert).result()

    assert openai_api._allow_streamlit_access() is True
