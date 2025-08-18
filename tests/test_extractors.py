import io
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
