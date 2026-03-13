from __future__ import annotations

import json
from typing import Any

import generators.interview_guide as interview_mod
import generators.job_ad as job_ad_mod


class _FakeResult:
    def __init__(self, content: str = "{}") -> None:
        self.content = content


def _job_ad_payload() -> str:
    return json.dumps(
        {
            "metadata": {"tone": "professional", "target_audience": "Engineers"},
            "ad": {
                "sections": {
                    "overview": "Overview",
                    "responsibilities": ["Build features"],
                    "requirements": ["Python"],
                    "how_to_apply": "Apply",
                    "equal_opportunity_statement": "Equal opportunity",
                }
            },
        }
    )


def test_job_ad_generator_uses_confirmed_only_payload(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def fake_call(*_args: Any, **kwargs: Any) -> _FakeResult:
        captured["messages"] = kwargs["messages"]
        return _FakeResult(content=_job_ad_payload())

    monkeypatch.setattr(job_ad_mod, "call_chat_api", fake_call)
    monkeypatch.setattr(job_ad_mod, "get_model_for", lambda *_, **__: "model-job-ad")

    job_ad_mod.generate_job_ad(
        {
            "role": {"title": "Existing"},
            "open_decisions": [
                {
                    "decision_id": "proposed",
                    "title": "Role",
                    "field_path": "role.title",
                    "decision_state": "proposed",
                    "proposed_value": "ShouldNotAppear",
                    "rationale": "pending",
                    "blocking_exports": ["job_ad_markdown"],
                },
                {
                    "decision_id": "confirmed",
                    "title": "Role",
                    "field_path": "role.title",
                    "decision_state": "confirmed",
                    "proposed_value": "ShouldAppear",
                    "rationale": "ok",
                    "blocking_exports": ["job_ad_markdown"],
                },
            ],
            "constraints": {"compensation_currency": "EUR", "benefits_overlay": ["public_transport_support"]},
            "warnings": [],
        },
        "de",
    )

    user_message = captured["messages"][1]["content"]
    assert "ShouldAppear" in user_message
    assert "ShouldNotAppear" not in user_message
    assert "'decision_state': 'proposed'" not in user_message
    assert "public_transport_support" in user_message


def test_interview_generator_adds_warning_for_blocking_proposed(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def fake_call(*_args: Any, **kwargs: Any) -> _FakeResult:
        captured["messages"] = kwargs["messages"]
        return _FakeResult(content="{}")

    monkeypatch.setattr(interview_mod, "call_chat_api", fake_call)
    monkeypatch.setattr(interview_mod, "get_model_for", lambda *_, **__: "model-interview")

    interview_mod.generate_interview_guide(
        {
            "open_decisions": [
                {
                    "decision_id": "d-int",
                    "title": "Panel",
                    "field_path": "selection.stakeholders",
                    "decision_state": "proposed",
                    "proposed_value": ["VP Eng"],
                    "rationale": "pending",
                    "blocking_exports": ["interview_guide"],
                }
            ],
            "warnings": [],
        },
        "en",
    )

    user_message = captured["messages"][1]["content"]
    assert "d-int" in user_message
    assert "warnings" in user_message


def test_job_ad_generator_uses_confirmed_location_decision_for_markdown_export(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def fake_call(*_args: Any, **kwargs: Any) -> _FakeResult:
        captured["messages"] = kwargs["messages"]
        return _FakeResult(content=_job_ad_payload())

    monkeypatch.setattr(job_ad_mod, "call_chat_api", fake_call)
    monkeypatch.setattr(job_ad_mod, "get_model_for", lambda *_, **__: "model-job-ad")

    job_ad_mod.generate_job_ad(
        {
            "role": {"work_location": "Berlin"},
            "open_decisions": [
                {
                    "decision_id": "loc-proposed",
                    "title": "Work location",
                    "field_path": "role.work_location",
                    "decision_state": "proposed",
                    "proposed_value": "Munich",
                    "rationale": "pending",
                    "blocking_exports": ["job_ad_markdown"],
                },
                {
                    "decision_id": "loc-confirmed",
                    "title": "Work location",
                    "field_path": "role.work_location",
                    "decision_state": "confirmed",
                    "proposed_value": "Hamburg",
                    "rationale": "approved",
                    "blocking_exports": ["job_ad_markdown"],
                },
            ],
            "warnings": [],
        },
        "en",
    )

    user_message = captured["messages"][1]["content"]
    assert "Hamburg" in user_message
    assert "Munich" not in user_message
