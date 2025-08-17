import fitz
from io import BytesIO
import docx

import utils


class DummyFile:
    def __init__(self, data: bytes, name: str) -> None:
        self._data = data
        self.name = name

    def read(self) -> bytes:
        return self._data


def test_extract_text_from_file_pdf():
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Hello PDF")
    pdf_bytes = doc.tobytes()
    text = utils.extract_text_from_file(DummyFile(pdf_bytes, "sample.pdf"))
    assert "Hello PDF" in text


def test_extract_text_from_file_docx():
    document = docx.Document()
    document.add_paragraph("Hello DOCX")
    buffer = BytesIO()
    document.save(buffer)
    text = utils.extract_text_from_file(DummyFile(buffer.getvalue(), "sample.docx"))
    assert "Hello DOCX" in text


def test_extract_text_from_url(monkeypatch):
    html = (
        "<html><body><h1>Title</h1><p>Hello URL</p><script>nope</script></body></html>"
    )

    class Resp:
        text = html

        def raise_for_status(self) -> None:  # pragma: no cover - noop
            return None

    def fake_get(_url, timeout):  # pragma: no cover - test stub
        return Resp()

    import requests

    monkeypatch.setattr(requests, "get", fake_get)

    text = utils.extract_text_from_url("http://example.com")
    assert "Hello URL" in text
