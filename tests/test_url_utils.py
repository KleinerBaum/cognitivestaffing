import pytest

import utils


def test_extract_text_from_url(monkeypatch: pytest.MonkeyPatch) -> None:
    html = (
        "<html><body><h1>Title</h1><p>Hello URL</p><script>nope</script></body></html>"
    )

    class Resp:
        text = html

        def raise_for_status(self) -> None:  # pragma: no cover - noop
            return None

    def fake_get(
        _url: str, timeout: float, headers: dict | None = None
    ):  # pragma: no cover - test stub
        return Resp()

    import requests

    monkeypatch.setattr(requests, "get", fake_get)

    text = utils.extract_text_from_url("http://example.com")
    assert "Hello URL" in text
