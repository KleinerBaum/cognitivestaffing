from core import ocr_backends
import pytest


def test_openai_backend(monkeypatch):
    class DummyResp:
        output_text = "text"

    class DummyClient:
        def __init__(self):
            self.responses = self

        def create(self, model, input):  # noqa: ARG002
            return DummyResp()

    monkeypatch.setattr(ocr_backends, "OpenAI", lambda: DummyClient())
    assert ocr_backends.extract_text(b"data", backend="openai") == "text"


def test_none_backend():
    assert ocr_backends.extract_text(b"bytes", backend="none") == ""


def test_unknown_backend():
    with pytest.raises(ValueError):
        ocr_backends.extract_text(b"data", backend="unknown")
