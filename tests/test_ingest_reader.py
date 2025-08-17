from ingest.reader import read_job_text


def test_read_job_text_merges_and_cleans(tmp_path):
    txt = tmp_path / "a.txt"
    txt.write_text("Hello   world\n")
    result = read_job_text([str(txt)], pasted="Hello world")
    assert result == "Hello world"
