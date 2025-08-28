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

    class Dummy:
        def model_dump_json(self, indent: int = 2) -> str:
            return '{"ok": true}'

    def fake_extract_and_parse(
        text: str, title: str | None = None, url: str | None = None
    ) -> Dummy:
        assert text == "TEXT"
        return Dummy()

    monkeypatch.setattr(
        "ingest.extractors.extract_text_from_file", fake_extract_text_from_file
    )
    monkeypatch.setattr("llm.client.extract_and_parse", fake_extract_and_parse)
    monkeypatch.setattr(sys, "argv", ["prog", "--file", str(sample)])

    cli_extract.main()

    assert called["used"]
    assert capsys.readouterr().out.strip() == '{"ok": true}'
