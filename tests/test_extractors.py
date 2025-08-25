import io
import sys
import types
from pypdf import PdfWriter

from ingest.extractors import extract_text_from_file


def test_extract_txt() -> None:
    f = io.BytesIO(b"Hello")
    f.name = "a.txt"
    assert extract_text_from_file(f) == "Hello"


def test_extract_txt_encoding_and_normalization() -> None:
    data = "Hällo\r\nWorld  ".encode("latin-1")
    f = io.BytesIO(data)
    f.name = "b.txt"
    assert extract_text_from_file(f) == "Hällo\nWorld"


def _blank_pdf() -> io.BytesIO:
    writer = PdfWriter()
    writer.add_blank_page(width=10, height=10)
    buf = io.BytesIO()
    writer.write(buf)
    buf.seek(0)
    buf.name = "c.pdf"
    return buf


def test_extract_pdf_with_ocr(monkeypatch) -> None:
    f = _blank_pdf()
    pdf2image = types.SimpleNamespace(convert_from_bytes=lambda *a, **k: [object()])
    pytesseract = types.SimpleNamespace(image_to_string=lambda img: "OCR TEXT")
    monkeypatch.setitem(sys.modules, "pdf2image", pdf2image)
    monkeypatch.setitem(sys.modules, "pytesseract", pytesseract)
    assert extract_text_from_file(f) == "OCR TEXT"
