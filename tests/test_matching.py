from __future__ import annotations

from pipelines import match_candidates


def _vacancy_payload() -> dict:
    return {
        "vacancy_id": "vac-1",
        "requirements": {
            "hard_skills_required": ["Python", "Kubernetes"],
            "hard_skills_optional": ["Terraform"],
            "soft_skills_required": ["Collaboration"],
            "languages_required": ["English"],
        },
        "position": {"seniority": "Senior"},
        "experience": {"years_min": 5},
        "location": {"primary_city": "Berlin", "country": "Germany"},
        "employment": {"work_policy": "hybrid"},
    }


def _candidate(
    candidate_id: str,
    skills: list[str],
    *,
    years: float | None = None,
    location: str | None = None,
    languages: list[str] | None = None,
) -> dict:
    return {
        "candidate": {
            "id": candidate_id,
            "name": candidate_id,
            "location": location,
            "total_years_experience": years,
        },
        "skills": [{"name": skill} for skill in skills],
        "languages": [{"code": lang} for lang in languages or []],
    }


def test_match_candidates_penalises_missing_must_have_and_populates_gaps() -> None:
    vacancy = _vacancy_payload()
    strong = _candidate(
        "cand-strong",
        ["Python", "Kubernetes", "Terraform", "Collaboration"],
        years=8,
        location="Berlin, Germany",
        languages=["en"],
    )
    weak = _candidate(
        "cand-weak",
        ["python"],
        years=8,
        location="Berlin, Germany",
        languages=["en"],
    )

    result = match_candidates(vacancy, [weak, strong])
    assert [entry["candidate_id"] for entry in result["candidates"]] == ["cand-strong", "cand-weak"]

    weak_entry = next(entry for entry in result["candidates"] if entry["candidate_id"] == "cand-weak")
    assert any("Missing must-have skill" in gap for gap in weak_entry["gaps"])
    assert any("must-have" in reason for reason in weak_entry["reasons"])
    assert weak_entry["score"] < 60
    assert weak_entry["score"] < result["candidates"][0]["score"]


def test_match_candidates_flags_language_and_experience_gaps() -> None:
    vacancy = _vacancy_payload()
    vacancy["requirements"]["languages_required"] = ["English", "German"]
    vacancy["experience"] = {"years_min": 7}

    candidate = _candidate(
        "cand-gap",
        ["Python", "Kubernetes", "Collaboration"],
        years=3,
        location="Munich, Germany",
        languages=["en"],
    )

    result = match_candidates(vacancy, [candidate])
    entry = result["candidates"][0]
    assert any("Missing required language" in gap for gap in entry["gaps"])
    assert any("Requires" in gap and "years" in gap for gap in entry["gaps"])
    assert entry["score"] < 80


def test_experience_inferred_from_experience_section() -> None:
    vacancy = _vacancy_payload()
    vacancy["experience"] = {"years_min": 4}
    vacancy["position"] = {}

    candidate = _candidate(
        "cand-exp",
        ["Python", "Kubernetes", "Collaboration"],
        years=3,
        location="Hamburg, Germany",
        languages=["en"],
    )

    result = match_candidates(vacancy, [candidate])
    entry = result["candidates"][0]
    assert any("Requires 4.0+ years" in gap for gap in entry["gaps"])
    assert any("Experience alignment" in reason for reason in entry["reasons"])
    assert entry["score"] < 80
