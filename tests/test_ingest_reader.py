from ingest.reader import clean_job_text, read_job_text


def test_read_job_text_merges_and_cleans(tmp_path):
    txt = tmp_path / "a.txt"
    txt.write_text("Hello   world\n")
    result = read_job_text([str(txt)], pasted="Hello world")
    assert result == "Hello world"


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
