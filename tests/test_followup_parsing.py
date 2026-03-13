from __future__ import annotations

import json

from utils.json_repair import JsonRepairStatus
from wizard.planner.plan_context import PlanContext
from wizard.services import followups as followups_mod


def _payload() -> dict[str, object]:
    return {
        "questions": [
            {
                "field": "company.name",
                "question": "What is the company name?",
                "priority": "critical",
                "suggestions": ["ACME"],
            }
        ]
    }


def test_parse_followups_valid_json() -> None:
    result = followups_mod._parse_followup_response(json.dumps(_payload()))
    assert result.fallback_reason is None
    assert result.payload["questions"][0]["field"] == "company.name"


def test_parse_followups_json_fence() -> None:
    fenced = f"```json\n{json.dumps(_payload())}\n```"
    result = followups_mod._parse_followup_response(fenced)
    assert result.fallback_reason is None
    assert result.payload["questions"][0]["question"].startswith("What is")


def test_parse_followups_trailing_commas() -> None:
    trailing = (
        '{"questions": [{"field": "company.name", "question": "Name?", '
        '"priority": "critical", "suggestions": ["ACME",],},],}'
    )
    result = followups_mod._parse_followup_response(trailing)
    assert result.fallback_reason is None
    assert result.repair_status is JsonRepairStatus.REPAIRED


def test_parse_followups_leading_prose() -> None:
    prose = f"Here are the questions:\n{json.dumps(_payload())}"
    result = followups_mod._parse_followup_response(prose)
    assert result.fallback_reason is None
    assert result.payload["questions"][0]["priority"] == "critical"


def test_parse_followups_missing_required_key() -> None:
    invalid = {
        "questions": [
            {
                "field": "company.name",
                "priority": "critical",
                "suggestions": ["ACME"],
            }
        ]
    }
    result = followups_mod._parse_followup_response(json.dumps(invalid))
    assert result.fallback_reason == "schema_invalid"
    assert result.error_reason == "schema_invalid"
    assert result.validation_errors


def test_parse_followups_deduplicates_fields() -> None:
    payload = {
        "questions": [
            {
                "field": "company.name",
                "question": "What is the company name?",
                "priority": "critical",
                "suggestions": ["ACME"],
            },
            {
                "field": "company.name",
                "question": "Please confirm company name.",
                "priority": "normal",
                "suggestions": ["ACME GmbH"],
            },
        ]
    }

    result = followups_mod._parse_followup_response(json.dumps(payload))

    assert result.fallback_reason is None
    questions = result.payload["questions"]
    assert len(questions) == 1
    assert questions[0]["field"] == "company.name"
    assert questions[0]["question"] == "What is the company name?"


def test_parse_followups_normalizes_legacy_field_aliases() -> None:
    payload = {
        "questions": [
            {
                "field": "position.location",
                "question": "Where is the role located?",
                "priority": "normal",
                "suggestions": ["Berlin"],
            },
            {
                "field": "position.context",
                "question": "What is the role context?",
                "priority": "normal",
                "suggestions": ["Platform team"],
            },
        ]
    }

    result = followups_mod._parse_followup_response(json.dumps(payload))

    assert result.fallback_reason is None
    fields = [item["field"] for item in result.payload["questions"]]
    assert fields == ["location.primary_city", "position.role_summary"]


def test_prioritize_followups_prefers_low_confidence_critical_fields() -> None:
    profile = {
        "company": {"name": "ACME"},
        "location": {"country": "DE"},
        "meta": {
            "field_metadata": {
                "location.country": {
                    "source": "heuristic",
                    "confidence": 0.2,
                    "confirmed": False,
                },
                "company.name": {
                    "source": "user",
                    "confidence": 1.0,
                    "confirmed": True,
                    "evidence_snippet": "ACME",
                },
            }
        },
    }
    questions = [
        {
            "field": "company.name",
            "question": "Confirm company name",
            "priority": "critical",
            "suggestions": ["ACME"],
        },
        {
            "field": "location.country",
            "question": "Confirm country",
            "priority": "normal",
            "suggestions": ["DE"],
        },
    ]

    result = followups_mod._prioritize_heuristic_followups(questions, profile=profile)

    assert result[0]["field"] == "location.country"


def test_prioritize_followups_is_deterministic_for_same_profile() -> None:
    profile = {
        "company": {"name": "ACME"},
        "meta": {"field_metadata": {}},
    }
    questions = [
        {"field": "company.name", "question": "Confirm company name", "priority": "normal"},
        {"field": "company.name", "question": "confirm company name", "priority": "normal"},
        {"field": "location.country", "question": "Confirm country", "priority": "normal"},
    ]

    first = followups_mod._prioritize_heuristic_followups(list(questions), profile=profile)
    second = followups_mod._prioritize_heuristic_followups(list(questions), profile=profile)

    assert [item["field"] + ":" + item["question"] for item in first] == [
        item["field"] + ":" + item["question"] for item in second
    ]


def test_prioritize_followups_plan_context_changes_ordering(monkeypatch) -> None:
    monkeypatch.setattr(followups_mod, "load_critical_fields", lambda: [])

    class _Score:
        def __init__(self) -> None:
            self.ui_behavior = "ok"
            self.score = 0.5

    monkeypatch.setattr(followups_mod, "compute_field_score", lambda *args, **kwargs: _Score())
    monkeypatch.setattr(followups_mod, "is_unconfirmed_low_confidence_heuristic", lambda *_args, **_kwargs: False)

    profile = {
        "meta": {"field_metadata": {}},
    }
    questions = [
        {"field": "location.primary_city", "question": "Confirm city", "priority": "normal"},
        {"field": "process.recruitment_timeline", "question": "Confirm timeline", "priority": "normal"},
    ]

    neutral = followups_mod._prioritize_heuristic_followups(list(questions), profile=profile)
    urgency_context = PlanContext(hiring_urgency="urgent")
    urgency = followups_mod._prioritize_heuristic_followups(
        list(questions),
        profile=profile,
        plan_context=urgency_context,
    )

    assert [item["field"] for item in neutral] == ["location.primary_city", "process.recruitment_timeline"]
    assert [item["field"] for item in urgency] == ["process.recruitment_timeline", "location.primary_city"]


def test_prioritize_followups_plan_context_role_and_location(monkeypatch) -> None:
    monkeypatch.setattr(followups_mod, "load_critical_fields", lambda: [])

    class _Score:
        def __init__(self) -> None:
            self.ui_behavior = "ok"
            self.score = 0.5

    monkeypatch.setattr(followups_mod, "compute_field_score", lambda *args, **kwargs: _Score())
    monkeypatch.setattr(followups_mod, "is_unconfirmed_low_confidence_heuristic", lambda *_args, **_kwargs: False)

    profile = {"meta": {"field_metadata": {}}}

    role_questions = [
        {"field": "location.primary_city", "question": "Confirm city", "priority": "normal"},
        {"field": "position.role_summary", "question": "Confirm role summary", "priority": "normal"},
    ]
    role_neutral = followups_mod._prioritize_heuristic_followups(list(role_questions), profile=profile)
    role_contextual = followups_mod._prioritize_heuristic_followups(
        list(role_questions),
        profile=profile,
        plan_context=PlanContext(role_family="engineering"),
    )

    assert [item["field"] for item in role_neutral] == ["location.primary_city", "position.role_summary"]
    assert [item["field"] for item in role_contextual] == ["position.role_summary", "location.primary_city"]

    location_questions = [
        {"field": "employment.work_policy", "question": "Confirm work policy", "priority": "normal"},
        {"field": "location.primary_city", "question": "Confirm city", "priority": "normal"},
    ]
    location_neutral = followups_mod._prioritize_heuristic_followups(
        list(location_questions),
        profile=profile,
    )
    location_contextual = followups_mod._prioritize_heuristic_followups(
        list(location_questions),
        profile=profile,
        plan_context=PlanContext(location="Berlin"),
    )

    assert [item["field"] for item in location_neutral] == ["employment.work_policy", "location.primary_city"]
    assert [item["field"] for item in location_contextual] == ["location.primary_city", "employment.work_policy"]


def test_prioritize_followups_plan_context_compliance_and_risk_signals(monkeypatch) -> None:
    monkeypatch.setattr(followups_mod, "load_critical_fields", lambda: [])

    class _Score:
        def __init__(self) -> None:
            self.ui_behavior = "ok"
            self.score = 0.5

    monkeypatch.setattr(followups_mod, "compute_field_score", lambda *args, **kwargs: _Score())
    monkeypatch.setattr(followups_mod, "is_unconfirmed_low_confidence_heuristic", lambda *_args, **_kwargs: False)

    profile = {"meta": {"field_metadata": {}}}
    questions = [
        {
            "field": "requirements.background_check_required",
            "question": "Is background check required?",
            "priority": "normal",
        },
        {
            "field": "location.primary_city",
            "question": "Confirm city",
            "priority": "normal",
        },
    ]

    neutral = followups_mod._prioritize_heuristic_followups(list(questions), profile=profile)
    risk_aware = followups_mod._prioritize_heuristic_followups(
        list(questions),
        profile=profile,
        plan_context=PlanContext(
            compliance=("gdpr",),
            risk_signals=("location mismatch", "compliance review"),
            location="Berlin",
        ),
    )

    assert [item["field"] for item in neutral] == [
        "location.primary_city",
        "requirements.background_check_required",
    ]
    assert [item["field"] for item in risk_aware] == [
        "requirements.background_check_required",
        "location.primary_city",
    ]
