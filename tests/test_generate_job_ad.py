from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import openai_utils


def test_generate_job_ad_includes_key_sections():
    session = {
        "position": {
            "job_title": "Software Engineer",
            "role_summary": "Build web apps",
            "team_size": 5,
        },
        "company": {
            "name": "Acme Corp",
            "mission": "Build the future of collaboration",
            "culture": "Inclusive and growth-oriented",
        },
        "location": {"primary_city": "Berlin"},
        "responsibilities": {"items": ["Develop features"]},
        "requirements": {"hard_skills_required": ["Python experience"]},
        "employment": {
            "work_policy": "Remote",
            "work_schedule": "Mon-Fri",
            "relocation_support": True,
            "visa_sponsorship": True,
        },
        "compensation": {
            "benefits": ["Stock options"],
            "salary_provided": True,
            "salary_min": 50000,
            "salary_max": 70000,
            "currency": "EUR",
            "period": "year",
        },
        "lang": "en",
    }

    output = openai_utils.generate_job_ad(
        session,
        selected_fields=[
            "position.job_title",
            "company.name",
            "location.primary_city",
            "position.role_summary",
            "responsibilities.items",
            "requirements.hard_skills_required",
            "employment.work_policy",
            "employment.work_schedule",
            "employment.relocation_support",
            "employment.visa_sponsorship",
            "position.team_size",
            "compensation.salary",
            "compensation.benefits",
        ],
        target_audience="Experienced engineers",
        manual_sections=[],
        lang="en",
    )

    assert output.startswith("# Software Engineer at Acme Corp")
    assert "**Location:** Berlin" in output
    assert "*Target audience: Experienced engineers*" in output
    assert "Build web apps" in output
    assert "## Requirements" in output
    assert "**Salary Range:** 50,000–70,000 EUR / year" in output
    assert "Stock options" in output


def test_generate_job_ad_includes_mission_and_culture_de():
    session = {
        "company": {
            "mission": "Weltklasse Produkte bauen",
            "culture": "Teamorientiert und offen",
        },
        "lang": "de",
    }

    output = openai_utils.generate_job_ad(
        session,
        selected_fields=["company.mission", "company.culture"],
        target_audience="Talente mit Teamgeist",
        manual_sections=[],
        lang="de",
    )

    assert "## Unternehmen" in output
    assert "**Mission:** Weltklasse Produkte bauen" in output
    assert "**Kultur:** Teamorientiert und offen" in output
    assert "*Zielgruppe: Talente mit Teamgeist*" in output


def test_generate_job_ad_formats_travel_and_remote_details():
    session_en = {
        "employment": {
            "travel_required": True,
            "travel_details": "Occasional (up to 10%)",
            "work_policy": "Hybrid",
        },
        "lang": "en",
    }

    output_en = openai_utils.generate_job_ad(
        session_en,
        selected_fields=[
            "employment.travel_required",
            "employment.work_policy",
        ],
        target_audience="Hybrid workers",
        manual_sections=[],
        lang="en",
    )
    assert "**Travel Requirements:** Occasional (up to 10%)" in output_en
    assert "**Work Policy:** Hybrid" in output_en

    session_de = {
        "employment": {
            "travel_required": True,
            "travel_details": "Gelegentlich (bis zu 10%)",
            "work_policy": "Hybrid",
            "work_policy_details": "3 Tage remote",
            "relocation_support": True,
        },
        "lang": "de",
    }

    output_de = openai_utils.generate_job_ad(
        session_de,
        selected_fields=[
            "employment.travel_required",
            "employment.work_policy",
            "employment.relocation_support",
        ],
        target_audience="Flexibel arbeitende Talente",
        manual_sections=[],
        lang="de",
    )
    assert "**Reisebereitschaft:** Gelegentlich (bis zu 10%)" in output_de
    assert "**Arbeitsmodell:** Hybrid (3 Tage remote)" in output_de
    assert "**Umzugsunterstützung:** Ja" in output_de


def test_generate_job_ad_uses_remote_percentage_hint():
    session = {
        "employment": {"work_policy": "Hybrid", "remote_percentage": 60},
        "lang": "en",
    }

    output = openai_utils.generate_job_ad(
        session,
        selected_fields=["employment.work_policy"],
        target_audience="Remote minded",
        manual_sections=[],
        lang="en",
    )

    assert "**Work Policy:** Hybrid (60% remote)" in output


def test_generate_job_ad_lists_unique_benefits():
    session = {
        "compensation": {
            "benefits": ["Gym membership", "Gym membership", "401(k) match"],
            "salary_provided": False,
        },
        "lang": "en",
    }

    output = openai_utils.generate_job_ad(
        session,
        selected_fields=["compensation.benefits"],
        target_audience="Benefit seekers",
        manual_sections=[],
        lang="en",
    )

    assert output.count("Gym membership") == 1
    assert "401(k) match" in output


def test_generate_job_ad_includes_manual_sections():
    session = {
        "position": {"job_title": "Product Manager"},
        "lang": "en",
    }

    output = openai_utils.generate_job_ad(
        session,
        selected_fields=["position.job_title"],
        target_audience="Experienced talent",
        manual_sections=[
            {"title": "Culture", "content": "We value openness."},
            {"content": "Flexible working hours."},
        ],
        lang="en",
    )

    assert "## Additional notes" in output
    assert "**Culture:**" in output
    assert "We value openness." in output
    assert "Flexible working hours." in output


def test_generate_job_ad_requires_data():
    session = {"lang": "en"}

    try:
        openai_utils.generate_job_ad(
            session,
            selected_fields=["position.job_title"],
            target_audience="General",
            manual_sections=[],
            lang="en",
        )
    except ValueError as exc:
        assert "No usable data" in str(exc)
    else:
        raise AssertionError("Expected ValueError when no content is available")
