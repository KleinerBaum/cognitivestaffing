from utils.normalization import classify_bullets


def test_classify_bullets_splits_responsibilities_and_requirements() -> None:
    items = [
        "Develop and maintain web applications.",
        "At least 3 years of experience with JavaScript.",
        "Lead a team of 5 engineers.",
        "Fluent in German and English.",
        "Excellent communication and teamwork abilities.",
    ]

    result = classify_bullets(items)

    assert result["responsibilities"] == [
        "Develop and maintain web applications.",
        "Lead a team of 5 engineers.",
    ]
    assert "3 years of experience" in " ".join(result["requirements"])
    assert any("Fluent in German" in req for req in result["requirements"])
    assert any("communication" in req for req in result["requirements"])
