"""Tests for schema repair during structured payload parsing."""

from __future__ import annotations

from unittest.mock import patch

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


def test_parse_structured_payload_forces_retry_for_required_skills() -> None:
    raw = '{"position": {"job_title": "Developer"}, "requirements": {"hard_skills_required": [], "soft_skills_required": []}}'
    source_text = "Requirements:\n- Python\n- Communication"
    retried_payload = {
        "position": {"job_title": "Developer"},
        "requirements": {
            "hard_skills_required": ["Python"],
            "soft_skills_required": ["Communication"],
        },
    }

    with patch("core.extraction.retry_profile_payload", return_value=retried_payload) as mocked_retry:
        payload, recovered, issues = parse_structured_payload(raw, source_text=source_text)

    assert mocked_retry.called
    assert recovered is True
    assert payload["position"]["job_title"] == "Developer"
    assert any("forced retry completed" in issue or "manual review required" in issue for issue in issues)


def test_parse_structured_payload_applies_compensation_and_remote_heuristics_en(
    monkeypatch,
) -> None:
    monkeypatch.setattr("core.extraction.repair_profile_payload", lambda *_, **__: None)
    monkeypatch.setattr("ingest.heuristics._llm_extract_primary_city", lambda _text: "")

    raw = '{"position": {"job_title": "Account Executive"}, "compensation": {"salary_min": null, "salary_max": null}}'
    source_text = (
        "Compensation: 90.000 - 110.000 € base + 20% bonus. Hybrid role with 3 office days per week and 2 days remote."
    )

    payload, _recovered, issues = parse_structured_payload(raw, source_text=source_text)

    compensation = payload["compensation"]
    employment = payload["employment"]
    location = payload["location"]

    assert compensation["salary_min"] == 90000
    assert compensation["salary_max"] == 110000
    assert compensation["currency"] == "EUR"
    assert compensation["bonus_percentage"] == 20
    assert compensation["salary_provided"] is True
    assert employment["remote_percentage"] == 40
    assert location["onsite_ratio"] == "60% onsite"
    assert any("compensation_and_remote: filled via heuristics" in issue for issue in issues)


def test_parse_structured_payload_applies_compensation_and_remote_heuristics_de(
    monkeypatch,
) -> None:
    monkeypatch.setattr("core.extraction.repair_profile_payload", lambda *_, **__: None)
    monkeypatch.setattr("ingest.heuristics._llm_extract_primary_city", lambda _text: "")

    raw = '{"position": {"job_title": "Projektmanager"}, "compensation": {"salary_min": null, "salary_max": null}}'
    source_text = (
        "Gehalt: 65.000 - 75.000 € jährlich plus 15% Bonus. Hybrid mit 2 Tagen Homeoffice und 3 Tagen im Büro."
    )

    payload, _recovered, _issues = parse_structured_payload(raw, source_text=source_text)

    assert payload["compensation"]["salary_min"] == 65000
    assert payload["compensation"]["salary_max"] == 75000
    assert payload["compensation"]["currency"] == "EUR"
    assert payload["compensation"]["bonus_percentage"] == 15
    assert payload["employment"]["remote_percentage"] == 40
    assert payload["location"]["onsite_ratio"] == "60% onsite"
