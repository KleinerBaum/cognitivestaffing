import io
from ingest.extractors import extract_text_from_file


def test_extract_txt() -> None:
    f = io.BytesIO(b"Hello")
    f.name = "a.txt"
    assert extract_text_from_file(f) == "Hello"
