from pathlib import Path
import sys

import pytest

from ingest.types import StructuredDocument
from config import ModelTask
import cli.extract as cli_extract


def test_cli_uses_ingest_extractor(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sample = tmp_path / "a.txt"
    sample.write_text("dummy")

    called: dict[str, bool] = {"used": False}

    def fake_extract_text_from_file(_fh) -> StructuredDocument:
        called["used"] = True
        return StructuredDocument(text="TEXT", blocks=[])

    class _Result:
        def __init__(self, data: dict[str, bool]) -> None:
            self.data = data

    def fake_extract_with_function(text: str, schema: dict, model=None, **kwargs):
        assert text == "TEXT"
        assert model == "router-model"
        return _Result({"ok": True})

    def fake_get_model_for(task: ModelTask) -> str:
        assert task is ModelTask.EXTRACTION
        return "router-model"

    monkeypatch.setattr("config.get_model_for", fake_get_model_for)
    monkeypatch.setattr(
        "ingest.extractors.extract_text_from_file", fake_extract_text_from_file
    )
    monkeypatch.setattr(
        "openai_utils.extract_with_function", fake_extract_with_function
    )
    monkeypatch.setattr("llm.rag_pipeline.build_field_queries", lambda _s: [])
    monkeypatch.setattr("llm.rag_pipeline.collect_field_contexts", lambda *a, **k: {})
    monkeypatch.setattr("llm.rag_pipeline.build_global_context", lambda *_a, **_k: [])
    monkeypatch.setattr(sys, "argv", ["prog", "--file", str(sample)])

    cli_extract.main()

    assert called["used"]
    assert capsys.readouterr().out.strip() == '{\n  "ok": true\n}'


def test_cli_handles_missing_ocr(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    sample = tmp_path / "scan.pdf"
    sample.write_bytes(b"PDF")

    message = (
        "scanned PDF extraction requires OCR support. Install pdf2image, "
        "pytesseract, and the Tesseract OCR engine, then retry."
    )

    def fake_extract_text_from_file(_fh):
        raise ValueError(message)

    monkeypatch.setattr(
        "ingest.extractors.extract_text_from_file", fake_extract_text_from_file
    )
    monkeypatch.setattr(sys, "argv", ["prog", "--file", str(sample)])

    with pytest.raises(SystemExit) as exc:
        cli_extract.main()
    assert exc.value.code == message
