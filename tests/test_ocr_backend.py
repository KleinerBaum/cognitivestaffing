import pytest
from ingest.ocr import (
    ocr_pdf,
    ocr_pdf_openai,
    ocr_pdf_textract,
    ocr_pdf_rapid,
    select_ocr_backend,
)


def test_select_known_backends():
    assert select_ocr_backend("tesseract") is ocr_pdf
    assert select_ocr_backend("openai") is ocr_pdf_openai
    assert select_ocr_backend("textract") is ocr_pdf_textract
    assert select_ocr_backend("rapidocr") is ocr_pdf_rapid


def test_select_unknown_backend():
    with pytest.raises(ValueError):
        select_ocr_backend("bogus")
