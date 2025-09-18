from pathlib import Path
import sys

import pytest

from ingest.types import StructuredDocument
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
        return _Result({"ok": True})

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
