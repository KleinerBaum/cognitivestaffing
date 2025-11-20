import json
from pathlib import Path
import sys
from typing import Any

from jsonschema import Draft202012Validator
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import ModelTask, get_model_for
from models import InterviewGuide
import openai_utils
from openai_utils import api
from schemas import INTERVIEW_GUIDE_SCHEMA


def _llm_payload(language: str) -> dict:
    if language.startswith("de"):
        return {
            "metadata": {
                "language": "de",
                "heading": "Interviewleitfaden – Ingenieur:in",
                "job_title": "Ingenieur:in",
                "audience": "general",
                "audience_label": "Allgemeines Interviewteam",
                "tone": "Strukturiert",
                "tone_label": "Strukturierter Ton",
                "culture_note": "Transparente Zusammenarbeit",
            },
            "focus_areas": [
                {
                    "label": "Schlüsselaufgaben",
                    "items": ["Systeme entwerfen"],
                }
            ],
            "evaluation_notes": [
                "Auf klare Struktur und Beispiele achten.",
                "Tonfall und Kulturfit bewerten.",
            ],
            "questions": [
                {
                    "question": "Beschreiben Sie Ihren Ansatz für komplexe Probleme.",
                    "focus": "Problemlösung",
                    "evaluation": "Achten Sie auf Struktur und Impact.",
                },
                {
                    "question": "Wie gestalten Sie teamübergreifende Zusammenarbeit?",
                    "focus": "Zusammenarbeit",
                    "evaluation": "Hören Sie auf klare Kommunikation.",
                },
            ],
        }
    return {
        "metadata": {
            "language": "en",
            "heading": "Interview Guide – Engineer",
            "job_title": "Engineer",
            "audience": "general",
            "audience_label": "General interview panel",
            "tone": "Casual",
            "tone_label": "Casual tone",
            "culture_note": "Collaborative and transparent",
        },
        "focus_areas": [
            {
                "label": "Key responsibilities",
                "items": ["Design systems", "Write code"],
            }
        ],
        "evaluation_notes": [
            "Probe for impact and measurable outcomes.",
            "Ensure collaboration examples match our culture.",
        ],
        "questions": [
            {
                "question": "Describe a time you solved a complex problem.",
                "focus": "Problem solving",
                "evaluation": "Look for structured reasoning and impact.",
            },
            {
                "question": "How do you collaborate across teams?",
                "focus": "Collaboration",
                "evaluation": "Listen for proactive communication.",
            },
            {
                "question": "What energises you outside of work?",
                "focus": "Motivation",
                "evaluation": "Ensure examples align with our values.",
            },
        ],
    }


def _assert_schema_forbids_extras(schema: Any) -> None:
    """Ensure JSON schema forbids additional properties on all objects."""

    def _check(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("type") == "object" or "properties" in node:
                assert node.get("additionalProperties") is False
            for value in node.values():
                _check(value)
        elif isinstance(node, list):
            for item in node:
                _check(item)

    _check(schema)


def test_generate_interview_guide_returns_llm_result(monkeypatch: pytest.MonkeyPatch) -> None:
    """The LLM driven path returns structured data validated against the schema."""

    captured: dict[str, object] = {}

    def fake_call(messages, **kwargs):
        captured["model"] = kwargs.get("model")
        captured["messages"] = messages
        captured["json_schema"] = kwargs.get("json_schema")
        captured["tools"] = kwargs.get("tools")
        captured["tool_choice"] = kwargs.get("tool_choice")
        payload = _llm_payload("en")
        return api.ChatCallResult(json.dumps(payload), [], {"input_tokens": 1})

    monkeypatch.setattr(openai_utils.api, "call_chat_api", fake_call)

    guide = openai_utils.generate_interview_guide(
        "Engineer",
        responsibilities="Design systems\nWrite code",
        hard_skills=["Python"],
        soft_skills=["Teamwork"],
        num_questions=4,
        lang="en",
        company_culture="Collaborative and transparent",
        tone="Casual",
        vector_store_id="store-1",
    )

    messages = captured["messages"]
    assert isinstance(messages, list) and len(messages) >= 2
    user_prompt = messages[1]["content"]
    assert (
        "at least one question covering responsibilities, hard skills, soft skills, and company culture" in user_prompt
    )
    assert "job title and seniority context" in user_prompt
    assert "Keep the guide in a Casual tone for the General interview panel audience." in user_prompt

    assert isinstance(guide, InterviewGuide)
    assert captured["model"] == get_model_for(ModelTask.INTERVIEW_GUIDE)
    assert guide.metadata.language == "en"
    assert guide.questions[0].question.startswith("Describe a time")
    assert guide.evaluation_notes
    markdown = guide.final_markdown()
    assert "Interview Guide – Engineer" in markdown
    assert "## Questions" in markdown or "## Questions & evaluation guide" in markdown
    assert "Evaluation notes" in markdown
    schema_cfg = captured["json_schema"]
    assert schema_cfg
    assert "schema" in schema_cfg
    _assert_schema_forbids_extras(schema_cfg["schema"])
    assert captured["tools"] == [
        {
            "type": "file_search",
            "name": "file_search",
            "vector_store_ids": ["store-1"],
            "file_search": {"vector_store_ids": ["store-1"]},
        }
    ]
    assert captured["tool_choice"] == "auto"


def test_generate_interview_guide_openai_schema_call(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure the OpenAI call receives the schema payload without errors."""

    captured: dict[str, Any] = {}

    def fake_call(messages: list[dict[str, Any]], **kwargs: Any) -> api.ChatCallResult:
        captured["json_schema"] = kwargs.get("json_schema")
        return api.ChatCallResult(json.dumps(_llm_payload("en")), [], {"input_tokens": 1})

    monkeypatch.setattr(openai_utils.api, "call_chat_api", fake_call)

    guide = openai_utils.generate_interview_guide(
        "Engineer",
        responsibilities="Design systems",
        hard_skills=["Python"],
        soft_skills=["Teamwork"],
        num_questions=3,
        lang="en",
        company_culture="Collaborative",
        tone="Structured",
    )

    schema_cfg = captured["json_schema"]
    assert schema_cfg
    assert schema_cfg.get("name") == "interviewGuide"
    assert schema_cfg.get("schema", {}).get("type") == "object"
    assert schema_cfg.get("schema", {}).get("additionalProperties") is False
    assert isinstance(guide, InterviewGuide)


def test_generate_interview_guide_handles_german_locale(monkeypatch: pytest.MonkeyPatch) -> None:
    """German prompts return localised metadata and Markdown."""

    def fake_call(messages, **kwargs):
        payload = _llm_payload("de")
        return api.ChatCallResult(json.dumps(payload), [], {"input_tokens": 1})

    monkeypatch.setattr(openai_utils.api, "call_chat_api", fake_call)

    guide = openai_utils.generate_interview_guide(
        "Ingenieur:in",
        responsibilities="Systeme entwerfen",
        hard_skills=["Python"],
        lang="de",
        num_questions=3,
        tone="Strukturiert",
        company_culture="Transparente Zusammenarbeit",
    )

    assert guide.metadata.language == "de"
    markdown = guide.final_markdown()
    assert "Interviewleitfaden" in markdown
    assert "Fragen & Bewertungsleitfaden" in markdown
    assert "Bewertungsschwerpunkte" in markdown


def test_generate_interview_guide_fallback_on_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Failures in the API call fall back to the deterministic generator."""

    def fail_call(*args, **kwargs):  # noqa: ANN001
        raise RuntimeError("offline")

    monkeypatch.setattr(openai_utils.api, "call_chat_api", fail_call)

    guide = openai_utils.generate_interview_guide(
        "Engineer",
        responsibilities="Design systems\nWrite code",
        hard_skills=["Python"],
        soft_skills=["Teamwork"],
        num_questions=3,
        lang="en",
        company_culture="Collaborative",
    )

    assert isinstance(guide, InterviewGuide)
    assert len(guide.questions) == 3
    markdown = guide.final_markdown()
    assert "Interview Guide" in markdown
    assert "Teamwork" in markdown or "Design systems" in markdown
    assert "Evaluation" in markdown


def test_interview_guide_model_dump_matches_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    """Model dumps must stay in sync with the InterviewGuide JSON schema."""

    validator = Draft202012Validator(INTERVIEW_GUIDE_SCHEMA)

    def fake_call(messages, **kwargs):  # noqa: ANN001
        payload = _llm_payload("en")
        return api.ChatCallResult(json.dumps(payload), [], {"input_tokens": 1})

    monkeypatch.setattr(openai_utils.api, "call_chat_api", fake_call)

    guide = openai_utils.generate_interview_guide(
        "Engineer",
        responsibilities="Design systems",
        hard_skills=["Python"],
        soft_skills=["Teamwork"],
        num_questions=2,
        lang="en",
        company_culture="Transparent",
    )

    payload = guide.model_dump(mode="json")
    validator.validate(payload)
