"""Tests for V2 intake diagnostics fast-path recommendation."""

from __future__ import annotations

from wizard.services.intake_diagnostics import evaluate_intake_diagnostics


def test_high_coverage_routes_directly_to_review_or_decision_board() -> None:
    profile = {
        "intake": {"raw_input": "Senior Python Engineer for platform team."},
        "role": {"title": "Senior Python Engineer", "summary": "Build and scale backend systems."},
        "work": {"responsibilities": ["Build APIs"], "location": "Berlin"},
        "requirements": {"hard_skills_required": ["Python", "FastAPI"]},
        "constraints": {"timeline": "Q2/2026", "salary_min": 70000, "salary_max": 90000},
        "selection": {"process_steps": ["Screen", "Tech interview", "Final"]},
    }

    result = evaluate_intake_diagnostics(profile)

    assert result.coverage >= 0.8
    assert result.recommendation == "review"
    assert result.focus_fields == ()


def test_medium_coverage_routes_to_focused_decisions() -> None:
    profile = {
        "intake": {"raw_input": "Need a backend engineer."},
        "role": {"title": "Backend Engineer", "summary": "TBD"},
        "work": {"responsibilities": ["Maintain APIs"]},
        "requirements": {"hard_skills_required": ["Python"]},
        "constraints": {"timeline": ""},
        "selection": {"process_steps": []},
    }

    result = evaluate_intake_diagnostics(profile)

    assert 0.45 <= result.coverage < 0.8
    assert result.recommendation == "decision_board"
    assert "role.summary" in result.ambiguities
    assert "constraints.timeline" in result.focus_fields
    assert "selection.process_steps" in result.focus_fields
