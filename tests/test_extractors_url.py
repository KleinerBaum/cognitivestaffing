import sys
import types

import pytest

from ingest.extractors import extract_text_from_url


def test_extract_text_from_url_success(monkeypatch: pytest.MonkeyPatch) -> None:
    html = "<html><body><p>Hello URL</p></body></html>"

    class Resp:
        status_code = 200
        text = html

        def raise_for_status(self) -> None:  # pragma: no cover - stub
            return None

    def fake_get(_url: str, timeout: float, headers: dict | None = None) -> Resp:
        return Resp()

    fake_traf = types.SimpleNamespace(
        extract=lambda *_args, **_kwargs: " Hello\n\nWorld "
    )

    monkeypatch.setattr("ingest.extractors.requests.get", fake_get)
    monkeypatch.setitem(sys.modules, "trafilatura", fake_traf)

    text = extract_text_from_url("http://example.com")
    assert text == "Hello\n\nWorld"


def test_extract_text_from_url_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    import requests
    from requests import Response

    def fake_get(
        _url: str, timeout: float, headers: dict | None = None
    ) -> Response:  # pragma: no cover - stub
        resp = Response()
        resp.status_code = 404
        resp._content = b""

        def raise_for_status() -> None:
            raise requests.HTTPError(response=resp)

        resp.raise_for_status = raise_for_status  # type: ignore[method-assign]
        return resp

    monkeypatch.setattr("ingest.extractors.requests.get", fake_get)
    monkeypatch.setitem(sys.modules, "trafilatura", None)

    with pytest.raises(ValueError) as err:
        extract_text_from_url("http://example.com")
    assert "status 404" in str(err.value)
