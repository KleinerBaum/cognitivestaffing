from pathlib import Path
import sys

import pytest

import cli.extract as cli_extract


def test_cli_uses_ingest_extractor(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sample = tmp_path / "a.txt"
    sample.write_text("dummy")

    called: dict[str, bool] = {"used": False}

    def fake_extract_text_from_file(_fh) -> str:
        called["used"] = True
        return "TEXT"

    def fake_extract_with_function(text: str, schema: dict, model=None):
        assert text == "TEXT"
        return {"ok": True}

    monkeypatch.setattr(
        "ingest.extractors.extract_text_from_file", fake_extract_text_from_file
    )
    monkeypatch.setattr(
        "openai_utils.extract_with_function", fake_extract_with_function
    )
    monkeypatch.setattr(sys, "argv", ["prog", "--file", str(sample)])

    cli_extract.main()

    assert called["used"]
    assert capsys.readouterr().out.strip() == '{\n  "ok": true\n}'
