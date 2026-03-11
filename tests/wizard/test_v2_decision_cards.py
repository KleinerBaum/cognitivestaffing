"""Flow tests for decision-first follow-up generation in V2."""

from __future__ import annotations

from wizard.planner.plan_context import PlanContext
from wizard.services.decision_engine import build_decision_backlog
from wizard.services.followups import generate_followups


def test_decision_first_prioritizes_blocking_search_then_selection() -> None:
    profile = {
        "company": {"name": "", "contact_email": "", "contact_phone": ""},
        "location": {"primary_city": ""},
        "open_decisions": [
            {
                "decision_id": "d-comm",
                "title": "Candidate messaging tone",
                "field_path": "selection.stakeholders",
                "decision_state": "proposed",
                "proposed_value": "friendly",
                "rationale": "pending alignment",
                "category": "candidate_communication",
                "impact_area": "Candidate-Communication",
                "blocking_exports": [],
                "suggested_resolution_options": ["friendly", "formal"],
            },
            {
                "decision_id": "d-search",
                "title": "Boolean search must-have terms",
                "field_path": "requirements.hard_skills_required",
                "decision_state": "proposed",
                "proposed_value": ["Python"],
                "rationale": "needed for sourcing",
                "category": "search",
                "impact_area": "Search",
                "blocking_exports": ["boolean_string", "job_ad_markdown"],
                "suggested_resolution_options": ["Python", "Python + SQL"],
            },
            {
                "decision_id": "d-selection",
                "title": "Interview panel composition",
                "field_path": "selection.process_steps",
                "decision_state": "proposed",
                "proposed_value": ["HM + Peer"],
                "rationale": "missing stakeholder sign-off",
                "category": "selection",
                "impact_area": "Selection",
                "blocking_exports": ["interview_guide"],
                "suggested_resolution_options": ["HM + Peer", "HM + Panel"],
            },
        ],
    }

    result = generate_followups(profile, locale="en", followup_mode="decision-first")

    assert result["source"] == "decision_backlog"
    questions = result["questions"]
    assert len(questions) == 3
    assert [item["decision_id"] for item in questions] == ["d-search", "d-selection", "d-comm"]
    assert all(
        item["field"] in {"requirements.hard_skills_required", "selection.process_steps", "selection.stakeholders"}
        for item in questions
    )


def test_decision_first_asks_few_targeted_questions_instead_of_microquestions() -> None:
    profile = {
        "company": {"name": "", "contact_email": "", "contact_phone": ""},
        "location": {"primary_city": ""},
        "requirements": {"hard_skills_required": [], "soft_skills_required": []},
        "open_decisions": [
            {
                "decision_id": "d-1",
                "title": "Finalize salary range",
                "field_path": "constraints.salary_min",
                "decision_state": "proposed",
                "proposed_value": 70000,
                "rationale": "budget unclear",
                "category": "selection",
                "impact_area": "Selection",
                "blocking_exports": ["job_ad_markdown"],
                "suggested_resolution_options": ["65k", "70k", "75k"],
            },
            {
                "decision_id": "d-2",
                "title": "Agree on outreach angle",
                "field_path": "role.summary",
                "decision_state": "proposed",
                "proposed_value": "impact-driven",
                "rationale": "messaging pending",
                "category": "candidate_communication",
                "impact_area": "Candidate-Communication",
                "blocking_exports": [],
                "suggested_resolution_options": ["impact-driven", "learning-focused"],
            },
            {
                "decision_id": "d-3",
                "title": "Decide core sourcing channels",
                "field_path": "work.location",
                "decision_state": "proposed",
                "proposed_value": "LinkedIn + referrals",
                "rationale": "search strategy open",
                "category": "search",
                "impact_area": "Search",
                "blocking_exports": ["boolean_string"],
                "suggested_resolution_options": ["LinkedIn + referrals", "LinkedIn + GitHub"],
            },
            {
                "decision_id": "d-4",
                "title": "Optional extra decision",
                "field_path": "selection.stakeholders",
                "decision_state": "proposed",
                "proposed_value": "TA Lead",
                "rationale": "not urgent",
                "category": "selection",
                "impact_area": "Selection",
                "blocking_exports": [],
                "suggested_resolution_options": ["TA Lead", "Hiring Manager"],
            },
        ],
    }

    result = generate_followups(profile, locale="de", followup_mode="decision-first", max_questions=3)

    assert result["source"] == "decision_backlog"
    assert len(result["questions"]) == 3
    selected_ids = {item["decision_id"] for item in result["questions"]}
    assert selected_ids == {"d-1", "d-3", "d-4"}
    assert "d-2" not in selected_ids


def test_decision_backlog_is_deterministic_for_same_input() -> None:
    decisions = [
        {
            "decision_id": "d-b",
            "title": "Timeline",
            "field_path": "process.recruitment_timeline",
            "decision_state": "proposed",
            "impact_area": "Selection",
            "blocking_exports": [],
        },
        {
            "decision_id": "d-a",
            "title": "Location",
            "field_path": "location.primary_city",
            "decision_state": "proposed",
            "impact_area": "Selection",
            "blocking_exports": [],
        },
    ]

    first = build_decision_backlog(decisions, max_items=2)
    second = build_decision_backlog(decisions, max_items=2)

    assert [card.decision_id for card in first] == [card.decision_id for card in second]


def test_decision_backlog_plan_context_changes_order() -> None:
    decisions = [
        {
            "decision_id": "d-timeline",
            "title": "Timeline",
            "field_path": "process.recruitment_timeline",
            "decision_state": "proposed",
            "impact_area": "Selection",
            "blocking_exports": [],
        },
        {
            "decision_id": "d-location",
            "title": "Location",
            "field_path": "location.primary_city",
            "decision_state": "proposed",
            "impact_area": "Selection",
            "blocking_exports": [],
        },
    ]

    neutral = build_decision_backlog(decisions, max_items=2)
    urgent = build_decision_backlog(
        decisions,
        max_items=2,
        plan_context=PlanContext(hiring_urgency="urgent"),
    )

    assert [card.decision_id for card in neutral] == ["d-location", "d-timeline"]
    assert [card.decision_id for card in urgent] == ["d-timeline", "d-location"]
