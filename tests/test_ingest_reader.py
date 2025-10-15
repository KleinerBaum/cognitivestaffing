import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ingest.reader import clean_job_text, read_job_text


def test_read_job_text_merges_and_cleans(tmp_path):
    txt = tmp_path / "a.txt"
    txt.write_text("Hello   world\n")
    result = read_job_text([str(txt)], pasted="Hello world")
    assert result.text == "Hello world"


def test_clean_job_text_removes_boilerplate():
    raw = "Home | Jobs | Karriere\n\nDeine Aufgaben\n- Analysieren\nImpressum\n"
    cleaned = clean_job_text(raw)
    assert "Home" not in cleaned
    assert "Impressum" not in cleaned
    assert "Deine Aufgaben" in cleaned


def test_clean_job_text_preserves_bullets():
    raw = "Menu\n\n- Verantwortung übernehmen\n- Analysieren"
    cleaned = clean_job_text(raw)
    assert cleaned.startswith("- Verantwortung übernehmen")
    assert "Analysieren" in cleaned


def test_clean_job_text_preserves_contact_lines():
    raw = (
        "Deine Aufgaben\n"
        "Kontakt: recruiting@example.com | https://example.com/kontakt\n"
        "Homepage: https://example.com/jobs\n"
    )
    cleaned = clean_job_text(raw)
    assert "Kontakt: recruiting@example.com | https://example.com/kontakt" in cleaned
    assert "Homepage: https://example.com/jobs" in cleaned


def test_clean_job_text_preserves_phone_number():
    raw = (
        "Bewirb dich jetzt!\n"
        "Telefon: +49 (0) 30 1234567\n"
        "Weitere Informationen findest du auf unserer Webseite.\n"
    )
    cleaned = clean_job_text(raw)
    assert "Telefon: +49 (0) 30 1234567" in cleaned


def test_read_job_text_raises_for_unsupported_extension(tmp_path):
    binary = tmp_path / "job.xls"
    binary.write_bytes(b"binary-data")

    with pytest.raises(ValueError) as excinfo:
        read_job_text([str(binary)])

    message = str(excinfo.value)
    assert "job.xls" in message
    assert "unsupported file type" in message.lower()
    assert "pdf" in message.lower()


def test_read_job_text_raises_for_unreachable_url(monkeypatch):
    url = "https://example.com/job"

    def _raise(_: str):
        raise ValueError("failed to fetch URL (status 500)")

    monkeypatch.setattr("ingest.reader.extract_text_from_url", _raise)

    with pytest.raises(ValueError) as excinfo:
        read_job_text([], url=url)

    message = str(excinfo.value)
    assert url in message
    assert "failed to fetch" in message.lower()
    assert "reachable" in message.lower()
