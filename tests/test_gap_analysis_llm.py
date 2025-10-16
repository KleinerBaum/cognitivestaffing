"""Unit tests for the gap analysis helper module."""

from __future__ import annotations

from pathlib import Path
import sys
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import llm.gap_analysis as gap_analysis  # noqa: E402
from openai_utils.api import ChatCallResult  # noqa: E402


def test_build_gap_prompt_includes_all_blocks():
    context = gap_analysis.GapContext(
        occupation={"preferredLabel": "Software Developer", "group": "ICT", "uri": "uri:123"},
        essential_skills=["Python", "Databases"],
        rag_snippets=["Snippet A", "Snippet B"],
    )

    messages = gap_analysis.build_gap_prompt(
        vacancy_text="We need engineers.",
        lang="en",
        job_title="Engineer",
        context=context,
    )

    assert messages[0]["role"] == "system"
    system_text = messages[0]["content"][0]["text"]
    assert "1. Vacancy snapshot" in system_text
    assert "4. Recommended next steps" in system_text

    user_blocks = messages[1]["content"]
    texts = [block["text"] for block in user_blocks]
    assert any(text.startswith("【VACANCY】") for text in texts)
    assert any(text.startswith("【ESCO】") for text in texts)
    assert any(text.startswith("【RAG】") for text in texts)


def test_retrieve_from_vector_store_parses_results(monkeypatch):
    captured: dict[str, object] = {}

    def fake_call(messages, **kwargs):  # noqa: ANN001 - simple stub
        captured["messages"] = messages
        captured["kwargs"] = kwargs
        return ChatCallResult(
            content=None,
            tool_calls=[],
            usage={},
            file_search_results=[
                {"text": "First snippet"},
                {"text": "Second snippet"},
            ],
        )

    monkeypatch.setattr(gap_analysis, "call_chat_api", fake_call)

    result = gap_analysis.retrieve_from_vector_store(
        "query",
        vector_store_id="store-123",
        client=object(),
        top_k=2,
    )
    assert result == ["First snippet", "Second snippet"]
    assert captured["kwargs"]["capture_file_search"] is True
    assert captured["kwargs"]["model"]


def test_analyze_vacancy_normalises_esco_and_skips_vector_store(monkeypatch):
    calls: dict[str, object] = {"normalize": None, "retrieve": 0}
    captured: dict[str, object] = {}

    def fake_classify(title: str, lang: str):
        assert title == "Engineer"
        assert lang == "en"
        return {"preferredLabel": "Engineer", "group": "Tech", "uri": "uri:1"}

    def fake_skills(uri: str, lang: str):
        assert uri == "uri:1"
        assert lang == "en"
        return [" Skill A ", "Skill B"]

    def fake_normalize(skills, lang: str):
        calls["normalize"] = (list(skills), lang)
        return ["Normalised"]

    def fake_retrieve(*_args, **_kwargs):
        calls["retrieve"] = calls.get("retrieve", 0) + 1
        return ["Should not appear"]

    monkeypatch.setattr(gap_analysis, "classify_occupation", fake_classify)
    monkeypatch.setattr(gap_analysis, "get_essential_skills", fake_skills)
    monkeypatch.setattr(gap_analysis, "normalize_skills", fake_normalize)
    monkeypatch.setattr(gap_analysis, "retrieve_from_vector_store", fake_retrieve)

    def fake_call_chat_api(messages, **kwargs):  # noqa: ANN001 - simple capture helper
        captured["messages"] = messages
        captured["kwargs"] = kwargs
        return ChatCallResult("# Report\n- Item", [], {"total_tokens": 12})

    monkeypatch.setattr(gap_analysis, "call_chat_api", fake_call_chat_api)

    result = gap_analysis.analyze_vacancy(
        " Vacancy text ",
        job_title="Engineer",
        lang="en",
        vector_store_id="",  # should skip retrieval and not increment counter
    )

    assert isinstance(result.content, str)
    assert result.content.startswith("# Report")
    assert result.usage == {"total_tokens": 12}

    assert calls["normalize"] == ([" Skill A ", "Skill B"], "en")
    assert calls["retrieve"] == 0

    assert captured["kwargs"]["tools"] is None
    assert captured["kwargs"]["tool_choice"] is None
    assert captured["kwargs"]["extra"] == {"metadata": {"task": "gap_analysis"}}

    captured = gap_analysis.build_gap_prompt(
        vacancy_text=" Vacancy text ",
        lang="en",
        job_title="Engineer",
        context=gap_analysis.GapContext(
            occupation={"preferredLabel": "Engineer"},
            essential_skills=["Normalised"],
            rag_snippets=[],
        ),
    )
    assert any("Normalised" in block["text"] for block in captured[1]["content"])


def test_analyze_vacancy_handles_service_failures(monkeypatch):
    def failing(*_args, **_kwargs):  # noqa: ANN001 - simple sentinel
        raise RuntimeError("boom")

    monkeypatch.setattr(gap_analysis, "classify_occupation", failing)
    monkeypatch.setattr(gap_analysis, "get_essential_skills", failing)
    monkeypatch.setattr(gap_analysis, "normalize_skills", failing)
    monkeypatch.setattr(gap_analysis, "retrieve_from_vector_store", failing)

    captured: dict[str, object] = {}

    def fake_call_chat_api(messages, **kwargs):  # noqa: ANN001 - capture helper
        captured["messages"] = messages
        captured["kwargs"] = kwargs
        return ChatCallResult("## Result", [], {})

    monkeypatch.setattr(gap_analysis, "call_chat_api", fake_call_chat_api)

    result = gap_analysis.analyze_vacancy(
        "Vacancy text",
        job_title="Title",
        lang="de",
        vector_store_id="store-1",
    )

    assert result.content == "## Result"
    assert captured["kwargs"]["tools"] == [
        {
            "type": "file_search",
            "name": "file_search",
            "vector_store_ids": ["store-1"],
        }
    ]
    assert captured["kwargs"]["tool_choice"] == "auto"


def test_analyze_vacancy_requires_text():
    with pytest.raises(ValueError):
        gap_analysis.analyze_vacancy(" ")
