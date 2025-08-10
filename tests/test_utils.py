import fitz
from io import BytesIO
import docx

import utils


def test_extract_text_from_file_pdf():
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Hello PDF")
    pdf_bytes = doc.tobytes()
    text = utils.extract_text_from_file(pdf_bytes, "sample.pdf")
    assert "Hello PDF" in text


def test_extract_text_from_file_docx():
    document = docx.Document()
    document.add_paragraph("Hello DOCX")
    buffer = BytesIO()
    document.save(buffer)
    text = utils.extract_text_from_file(buffer.getvalue(), "sample.docx")
    assert "Hello DOCX" in text


def test_extract_text_from_file_pdf_ocr(monkeypatch):
    doc = fitz.open()
    doc.new_page()
    pdf_bytes = doc.tobytes()

    import pytesseract

    def fake_ocr(_img):
        return "SCANNED TEXT"

    monkeypatch.setattr(pytesseract, "image_to_string", fake_ocr)
    text = utils.extract_text_from_file(pdf_bytes, "scan.pdf")
    assert "SCANNED TEXT" in text


def test_extract_text_from_url(monkeypatch):
    html = (
        "<html><body><h1>Title</h1><p>Hello URL</p>"
        "<script>nope</script></body></html>"
    )

    class Resp:
        status_code = 200
        text = html

    def fake_get(_url, timeout):
        return Resp()

    import requests
    monkeypatch.setattr(requests, "get", fake_get)

    import readability

    class DummyDoc:
        def __init__(self, text):
            self.text = text

        def summary(self):
            return self.text

    monkeypatch.setattr(readability, "Document", lambda html: DummyDoc(html))

    text = utils.extract_text_from_url("http://example.com")
    assert "Hello URL" in text and "nope" not in text
