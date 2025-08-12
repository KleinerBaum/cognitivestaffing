from nlp.prepare_text import truncate_smart


def test_truncate_preserves_paragraphs():
    text = "para1\n\npara2\n\npara3"
    max_chars = len("para1\n\npara2")
    result = truncate_smart(text, max_chars)
    assert result.endswith("para2")
    assert "para3" not in result


def test_truncate_preserves_bullets():
    text = "- a\n- b\n- c\n"
    max_chars = len("- a\n- b\n")
    result = truncate_smart(text, max_chars)
    assert result == "- a\n- b"
