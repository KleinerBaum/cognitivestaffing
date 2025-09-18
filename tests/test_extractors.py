import io
import sys
import types

import pytest
from pypdf import PdfWriter

from ingest.extractors import extract_text_from_file


def test_extract_txt() -> None:
    f = io.BytesIO(b"Hello")
    f.name = "a.txt"
    result = extract_text_from_file(f)
    assert result.text == "Hello"


def test_extract_txt_encoding_and_normalization() -> None:
    data = "Hällo\r\nWorld  ".encode("latin-1")
    f = io.BytesIO(data)
    f.name = "b.txt"
    result = extract_text_from_file(f)
    assert result.text == "Hällo\nWorld"


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
    assert extract_text_from_file(f).text == "OCR TEXT"


def test_extract_empty_file() -> None:
    f = io.BytesIO(b"")
    f.name = "d.txt"
    with pytest.raises(ValueError, match="empty file"):
        extract_text_from_file(f)


def test_extract_unsupported_type() -> None:
    f = io.BytesIO(b"data")
    f.name = "e.png"
    with pytest.raises(ValueError, match="unsupported file type"):
        extract_text_from_file(f)


def test_extract_invalid_pdf() -> None:
    f = io.BytesIO(b"not a pdf")
    f.name = "f.pdf"
    with pytest.raises(ValueError, match="invalid pdf"):
        extract_text_from_file(f)


def test_extract_file_too_large() -> None:
    big = io.BytesIO(b"x" * (21 * 1024 * 1024))
    big.name = "g.txt"
    with pytest.raises(ValueError, match="file too large"):
        extract_text_from_file(big)


def test_extract_pdf_missing_ocr(monkeypatch) -> None:
    f = _blank_pdf()
    import builtins

    orig_import = builtins.__import__

    def fake_import(name, *a, **k):
        if name in {"pdf2image", "pytesseract"}:
            raise ImportError("missing")
        return orig_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(RuntimeError, match="ocr dependencies"):
        extract_text_from_file(f)
