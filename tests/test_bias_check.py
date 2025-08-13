from nlp.bias import scan_bias_language


def test_scan_bias_language_flags_terms() -> None:
    text = "We are looking for a young and dynamic recent grad."
    findings = scan_bias_language(text, lang="en")
    terms = {item["term"] for item in findings}
    assert "young" in terms
    assert "recent grad" in terms


def test_scan_bias_language_no_terms() -> None:
    text = "We welcome applicants with diverse backgrounds."
    assert scan_bias_language(text) == []
