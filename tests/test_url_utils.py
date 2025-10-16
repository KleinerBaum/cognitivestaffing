import pytest

import utils
from utils.url_utils import is_supported_url


def test_extract_text_from_url(monkeypatch: pytest.MonkeyPatch) -> None:
    html = "<html><body><h1>Title</h1><p>Hello URL</p><script>nope</script></body></html>"

    class Resp:
        text = html

        def raise_for_status(self) -> None:  # pragma: no cover - noop
            return None

    def fake_get(_url: str, timeout: float, headers: dict | None = None):  # pragma: no cover - test stub
        return Resp()

    import requests

    monkeypatch.setattr(requests, "get", fake_get)

    text = utils.extract_text_from_url("http://example.com")
    assert "Hello URL" in text


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
