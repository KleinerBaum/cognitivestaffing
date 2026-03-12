"""Tests for heuristic collaboration/work-environment risk decision detection."""

from __future__ import annotations

from wizard.planner.plan_context import PlanContext
from wizard.planner.risk_detection import detect_risk_decision_cards
from wizard.services.followups import generate_followups


def test_detect_risk_cards_is_deterministic_for_fixture() -> None:
    profile = {
        "role": {
            "summary": "Cross-functional role with frequent escalation and confidential board updates.",
        },
        "selection": {
            "stakeholders": ["Hiring Manager", "TA", "Finance", "Works Council"],
        },
        "constraints": {
            "timeline": "ASAP hire needed",
        },
        "requirements": {
            "languages_required": ["German", "English"],
            "soft_skills_required": ["leadership", "autonomy"],
        },
        "evidence": [
            {
                "field_path": "role.summary",
                "excerpt": "Potential political sensitivity due to reorg.",
                "source": "import",
                "confidence": 0.7,
            }
        ],
    }

    first = detect_risk_decision_cards(profile, plan_context=PlanContext(risk_signals=("timeline pressure",)))
    second = detect_risk_decision_cards(profile, plan_context=PlanContext(risk_signals=("timeline pressure",)))

    assert [card.decision_id for card in first] == [card.decision_id for card in second]
    assert "risk-stakeholder_complexity" in [card.decision_id for card in first]
    assert "risk-pressure_patterns" in [card.decision_id for card in first]


def test_decision_first_uses_risk_cards_when_open_decisions_absent() -> None:
    profile = {
        "role": {"summary": "Need strong mediation skills for conflict-heavy interfaces."},
        "constraints": {"timeline": "Urgent hiring"},
        "selection": {"stakeholders": ["HM", "TA", "CFO"]},
    }

    result = generate_followups(
        profile,
        locale="en",
        followup_mode="decision-first",
        max_questions=2,
        call_llm=lambda *_args, **_kwargs: {"questions": []},
    )

    assert result["source"] == "decision_backlog"
    assert result["mode"] == "decision-first"
    assert len(result["questions"]) == 2
    ids = [item["decision_id"] for item in result["questions"]]
    assert ids == ["risk-pressure_patterns", "risk-conflict_heavy_interface"]


def test_risk_detection_does_not_mutate_profile() -> None:
    profile = {
        "role": {"summary": "Distributed async team across timezones."},
        "requirements": {"languages_required": ["English"]},
    }

    _ = detect_risk_decision_cards(profile)

    assert "open_decisions" not in profile
    assert profile["role"]["summary"] == "Distributed async team across timezones."
