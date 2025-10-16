import pytest

import utils
from utils.url_utils import is_supported_url
import utils.url_utils as url_utils


def _install_request_stub(monkeypatch: pytest.MonkeyPatch, html: str) -> None:
    class Resp:
        text = html

        def raise_for_status(self) -> None:  # pragma: no cover - noop
            return None

    def fake_get(_url: str, timeout: float, headers: dict | None = None):  # pragma: no cover - test stub
        return Resp()

    import requests

    monkeypatch.setattr(requests, "get", fake_get)


def test_extract_text_from_url(monkeypatch: pytest.MonkeyPatch) -> None:
    html = "<html><body><h1>Title</h1><p>Hello URL</p><script>nope</script></body></html>"
    _install_request_stub(monkeypatch, html)
    text = utils.extract_text_from_url("http://example.com")
    assert "Hello URL" in text
    assert "nope" not in text


def test_extract_text_from_url_without_beautifulsoup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    html = "<html><body><main><p>Fallback text</p></main><script>ignore me</script></body></html>"
    _install_request_stub(monkeypatch, html)
    monkeypatch.setattr(url_utils, "BeautifulSoup", None)
    text = utils.extract_text_from_url("http://example.com")
    assert "Fallback text" in text
    assert "ignore me" not in text


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/path?param=value#section",
        "http://example.com/über?foo=bar",
        "https://sub.example.com/%7Euser/index.html",
    ],
)
def test_is_supported_url_accepts_http_variants(url: str) -> None:
    assert is_supported_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.com/resource",
        "mailto:test@example.com",
        "https://",
        "",
    ],
)
def test_is_supported_url_rejects_invalid_urls(url: str) -> None:
    assert not is_supported_url(url)
