"""Tests for :func:`ingest.extractors._fetch_url`."""

from __future__ import annotations

from typing import Any, Callable
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


class DummySession:
    """Simple session stub capturing headers and cookies."""

    def __init__(self, handler: Callable[["DummySession", str, float, bool], DummyResponse]) -> None:
        self._handler = handler
        self.headers: dict[str, Any] = {}
        self.cookies: dict[str, str] = {}
        self.closed = False

    def __enter__(self) -> "DummySession":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: Any,
    ) -> None:
        self.close()

    def close(self) -> None:
        self.closed = True

    def get(self, url: str, *, timeout: float, allow_redirects: bool) -> DummyResponse:
        response = self._handler(self, url, timeout, allow_redirects)
        cookie_header = response.headers.get("Set-Cookie") or response.headers.get("set-cookie")
        if cookie_header:
            cookie_name, _, cookie_value = cookie_header.partition("=")
            value = cookie_value.split(";", 1)[0]
            if cookie_name:
                self.cookies[cookie_name] = value
        return response


def _patch_session(
    monkeypatch: pytest.MonkeyPatch, handler: Callable[["DummySession", str, float, bool], DummyResponse]
) -> DummySession:
    created_session = DummySession(handler)

    def _factory() -> DummySession:
        return created_session

    monkeypatch.setattr(requests, "Session", _factory)
    return created_session


def test_fetch_url_handles_redirect(monkeypatch: pytest.MonkeyPatch) -> None:
    """A redirect response is retried and the final body returned."""

    call_count = 0

    def handler(session: DummySession, url: str, timeout: float, allow_redirects: bool) -> DummyResponse:
        nonlocal call_count
        call_count += 1
        assert allow_redirects is False
        assert session.headers["User-Agent"] == "CognitiveNeeds/1.0"
        if call_count == 1:
            return DummyResponse(301, headers={"Location": "/final"})
        assert url == "https://example.com/final"
        return DummyResponse(200, text="done")

    session = _patch_session(monkeypatch, handler)

    assert _fetch_url("https://example.com/start") == "done"
    assert call_count == 2
    assert session.closed is True


def test_fetch_url_redirect_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exceeding the redirect limit raises a ``ValueError``."""

    def handler(session: DummySession, url: str, timeout: float, allow_redirects: bool) -> DummyResponse:
        assert allow_redirects is False
        return DummyResponse(302, headers={"Location": f"/next-{url.split('/')[-1]}"})

    _patch_session(monkeypatch, handler)

    with pytest.raises(ValueError, match="too many redirects"):
        _fetch_url("https://example.com/start")


def test_fetch_url_detects_redirect_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    """Alternating redirects surface a dedicated error message."""

    calls: list[str] = []

    def handler(session: DummySession, url: str, timeout: float, allow_redirects: bool) -> DummyResponse:
        calls.append(url)
        assert allow_redirects is False
        if url.endswith("start"):
            return DummyResponse(301, headers={"Location": "/second"})
        return DummyResponse(302, headers={"Location": "/start"})

    _patch_session(monkeypatch, handler)

    with pytest.raises(ValueError, match="redirect loop detected"):
        _fetch_url("https://example.com/start")

    assert calls == ["https://example.com/start", "https://example.com/second"]


def test_fetch_url_preserves_cookies_across_redirect(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cookies from redirects are persisted for subsequent requests."""

    call_count = 0

    def handler(session: DummySession, url: str, timeout: float, allow_redirects: bool) -> DummyResponse:
        nonlocal call_count
        call_count += 1
        assert allow_redirects is False
        if call_count == 1:
            assert "session" not in session.cookies
            return DummyResponse(
                302,
                headers={
                    "Location": "https://example.com/protected",
                    "Set-Cookie": "session=abc123; Path=/",
                },
            )
        if session.cookies.get("session") != "abc123":
            return DummyResponse(403, text="forbidden")
        return DummyResponse(200, text="secret")

    _patch_session(monkeypatch, handler)

    assert _fetch_url("https://example.com/start") == "secret"
    assert call_count == 2
