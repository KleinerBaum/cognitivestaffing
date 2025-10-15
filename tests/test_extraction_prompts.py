from __future__ import annotations

import base64
import sys
from io import BytesIO
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ingest.extractors import extract_text_from_file  # noqa: E402


_FIXTURE = Path("tests/fixtures/job_ad_simple_en_pdf_base64.txt")


def _load_pdf_fixture() -> BytesIO:
    encoded = _FIXTURE.read_text(encoding="utf-8").strip()
    data = base64.b64decode(encoded)
    buf = BytesIO(data)
    buf.name = "job_ad_simple_en.pdf"
    return buf


def test_extract_text_from_pdf_fixture() -> None:
    buffer = _load_pdf_fixture()
    document = extract_text_from_file(buffer)

    assert "Simple English Job Ad" in document.text
    assert "Software Engineer" in document.text
    assert "Build scalable APIs" in document.text
