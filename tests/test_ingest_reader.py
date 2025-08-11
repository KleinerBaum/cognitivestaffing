import fitz
from ingest.reader import read_job_text


def test_read_job_text_merges_and_cleans(tmp_path):
    txt = tmp_path / "a.txt"
    txt.write_text("Hello   world\n")
    result = read_job_text([str(txt)], pasted="Hello world")
    assert result == "Hello world"


def test_read_job_text_triggers_ocr(tmp_path, monkeypatch):
    pdf_path = tmp_path / "blank.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.save(pdf_path)
    doc.close()

    def fake_ocr(path: str) -> str:  # noqa: ARG001
        return "scanned text"

    monkeypatch.setattr("ingest.ocr.ocr_pdf", fake_ocr)
    result = read_job_text([str(pdf_path)], use_ocr=True)
    assert result == "scanned text"
