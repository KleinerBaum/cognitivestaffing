"""Tests for :func:`ingest.extractors._fetch_url`."""

from __future__ import annotations

from typing import Any
from pathlib import Path
import sys

import pytest
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ingest.extractors import _fetch_url  # noqa: E402


class DummyResponse:
    """Minimal response object mimicking ``requests.Response`` for tests."""

    def __init__(self, status_code: int, text: str = "", headers: dict[str, Any] | None = None) -> None:
        self.status_code = status_code
        self.text = text
        self.headers = headers or {}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(response=self)


def test_fetch_url_handles_redirect(monkeypatch: pytest.MonkeyPatch) -> None:
    """A redirect response is retried and the final body returned."""

    call_count = 0

    def fake_get(url: str, timeout: float, headers: dict[str, Any], allow_redirects: bool) -> DummyResponse:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            response = DummyResponse(301, headers={"Location": "/final"})
            raise requests.HTTPError(response=response)
        assert url == "https://example.com/final"
        return DummyResponse(200, text="done")

    monkeypatch.setattr(requests, "get", fake_get)

    assert _fetch_url("https://example.com/start") == "done"
    assert call_count == 2


def test_fetch_url_redirect_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exceeding the redirect limit raises a ``ValueError``."""

    def fake_get(url: str, timeout: float, headers: dict[str, Any], allow_redirects: bool) -> DummyResponse:
        response = DummyResponse(302, headers={"Location": "/loop"})
        raise requests.HTTPError(response=response)

    monkeypatch.setattr(requests, "get", fake_get)

    with pytest.raises(ValueError, match="too many redirects"):
        _fetch_url("https://example.com/start")
