"""Tests for schema repair during structured payload parsing."""

from __future__ import annotations

from core.extraction import parse_structured_payload


def test_parse_structured_payload_adds_missing_sections_and_defaults() -> None:
    """Missing sections should be filled and reported as issues."""

    payload, recovered, issues = parse_structured_payload('{"position": {"job_title": "Developer"}}')

    assert recovered is False
    assert payload["position"]["job_title"] == "Developer"
    assert "company" in payload
    assert payload["company"]["name"] is None
    assert any(
        entry.startswith("company:") or entry.startswith("company ") or entry.startswith("company.") for entry in issues
    )
    assert any("company.name" in entry for entry in issues)


def test_parse_structured_payload_sets_placeholders() -> None:
    payload, recovered, issues = parse_structured_payload("{}")

    assert recovered is False
    assert payload["company"]["name"] is None
    assert payload["company"]["contact_email"] == ""
    assert payload["location"]["primary_city"] == ""
    assert any("company.contact_email" in entry for entry in issues)
    assert any("location.primary_city" in entry for entry in issues)


def test_parse_structured_payload_fills_missing_lists_with_heuristics() -> None:
    raw = """
    {
        "position": {"job_title": "Account Manager"},
        "responsibilities": {"items": []},
        "requirements": {
            "hard_skills_required": [],
            "soft_skills_required": []
        }
    }
    """
    source_text = (
        "Ihre Aufgaben:\n"
        "- Kunden betreuen\n"
        "- Umsatz steigern\n"
        "\n"
        "Was du mitbringst:\n"
        "- Erfahrung im Vertrieb\n"
        "- Teamfähigkeit\n"
    )

    payload, _recovered, _issues = parse_structured_payload(raw, source_text=source_text)

    responsibilities = payload["responsibilities"]["items"]
    assert responsibilities
    assert any("Kunden betreuen" in item for item in responsibilities)

    requirements = payload["requirements"]
    assert requirements["hard_skills_required"] or requirements["soft_skills_required"]
    assert any("Vertrieb" in skill for skill in requirements["hard_skills_required"])
