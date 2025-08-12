import json
from io import BytesIO

import docx
import fitz

from utils.export import (
    prepare_download_data,
    text_to_docx,
    text_to_pdf,
    text_to_json,
)


def test_text_to_docx() -> None:
    data = text_to_docx("Hello")
    document = docx.Document(BytesIO(data))
    assert document.paragraphs[0].text == "Hello"


def test_text_to_pdf() -> None:
    data = text_to_pdf("Hello")
    doc = fitz.open(stream=data, filetype="pdf")
    assert doc.page_count == 1


def test_text_to_json() -> None:
    data = text_to_json("Hello", key="test", title="Title")
    obj = json.loads(data.decode("utf-8"))
    assert obj == {"type": "test", "content": "Hello", "title": "Title"}


def test_prepare_download_data_docx() -> None:
    data, mime, ext = prepare_download_data("Hello", "docx", key="test")
    assert ext == "docx"
    assert mime.startswith("application/vnd")
    document = docx.Document(BytesIO(data))
    assert document.paragraphs[0].text == "Hello"
