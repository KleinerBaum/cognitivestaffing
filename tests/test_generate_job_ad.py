import pytest

import openai_utils
from openai_utils.api import ChatCallResult


def _collect_prompt_text(messages: list[dict[str, str]]) -> str:
    return "\n".join(msg.get("content", "") for msg in messages)


def test_generate_job_ad_llm_prompt_carries_tone_and_brand(monkeypatch):
    captured: dict[str, list[dict[str, str]]] = {}

    def fake_call(messages, **_kwargs):
        captured["messages"] = messages
        return ChatCallResult(
            content=(
                "# Software Engineer at Acme Corp\n\n"
                "## Why you'll love working with us\n"
                "- Build meaningful products together\n\n"
                "**Ready to apply?**"
            ),
            tool_calls=[],
            usage={},
        )

    monkeypatch.setattr(openai_utils.api, "call_chat_api", fake_call)

    session = {
        "position": {
            "job_title": "Software Engineer",
            "role_summary": "Build and ship delightful web apps.",
        },
        "company": {
            "brand_keywords": "innovative spirit",
            "brand_name": "Acme Labs",
            "name": "Acme Corp",
            "mission": "Build the future of collaboration",
        },
        "location": {"primary_city": "Berlin"},
        "responsibilities": {"items": ["Develop features", "Review code"]},
        "requirements": {"hard_skills_required": ["Python"]},
        "lang": "en",
    }

    output = openai_utils.generate_job_ad(
        session,
        selected_fields=[
            "position.job_title",
            "company.brand_name",
            "company.mission",
            "location.primary_city",
            "position.role_summary",
            "responsibilities.items",
            "requirements.hard_skills_required",
        ],
        target_audience="Experienced engineers",
        manual_sections=[{"title": "Culture", "content": "We celebrate learning."}],
        style_reference="Bold and human",
        tone="creative",
        lang="en",
    )

    assert output.startswith("# Software Engineer at Acme Corp")
    assert "Ready to apply?" in output
    prompt_text = _collect_prompt_text(captured["messages"])
    assert "creative" in prompt_text.lower()
    assert "bold and human" in prompt_text.lower()
    assert "innovative spirit" in prompt_text.lower()
    assert "Culture: We celebrate learning." in prompt_text
    assert "Experienced engineers" in prompt_text


def test_generate_job_ad_fallback_highlights_tone_and_cta(monkeypatch):
    def failing_call(*_args, **_kwargs):  # pragma: no cover - behaviour exercised
        raise RuntimeError("API disabled for test")

    monkeypatch.setattr(openai_utils.api, "call_chat_api", failing_call)

    session = {
        "company": {
            "name": "Beispiel GmbH",
            "brand_keywords": ["inklusive Sprache", "Teamgeist"],
        },
        "employment": {"work_policy": "Hybrid", "remote_percentage": 60},
        "lang": "de",
    }

    output = openai_utils.generate_job_ad(
        session,
        selected_fields=[
            "company.name",
            "employment.work_policy",
            "employment.remote_percentage",
        ],
        target_audience="Talente mit Teamgeist",
        manual_sections=[],
        style_reference=None,
        tone="diversity_focused",
        lang="de",
    )

    lines = output.splitlines()
    assert lines[0].startswith("#")
    assert any("zielgruppe" in line.lower() for line in lines)
    assert any("ton" in line.lower() for line in lines)
    assert "bewirb" in output.lower()
    assert "Teamgeist" in output


def test_generate_job_ad_requires_content():
    with pytest.raises(ValueError):
        openai_utils.generate_job_ad(
            {"lang": "en"},
            selected_fields=["company.name"],
            target_audience="General",
            manual_sections=[],
            style_reference=None,
            tone="formal",
            lang="en",
        )


def test_stream_job_ad_returns_stream(monkeypatch):
    class _FakeStream:
        def __init__(self) -> None:
            self._chunks = ["Hello world"]

        def __iter__(self):
            yield from self._chunks

        @property
        def result(self) -> ChatCallResult:
            return ChatCallResult("Hello world", [], {"input_tokens": 0, "output_tokens": 0})

        @property
        def text(self) -> str:
            return "Hello world"

    monkeypatch.setattr(openai_utils.api, "stream_chat_api", lambda *a, **k: _FakeStream())

    session = {
        "position": {"job_title": "Engineer"},
        "company": {"name": "Acme"},
        "lang": "en",
    }

    stream, fallback = openai_utils.stream_job_ad(
        session,
        selected_fields=["position.job_title", "company.name"],
        target_audience="Builders",
        manual_sections=[],
        style_reference=None,
        tone="formal",
        lang="en",
    )

    assert list(stream) == ["Hello world"]
    assert fallback.startswith("#")
