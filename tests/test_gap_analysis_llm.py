"""Unit tests for the gap analysis helper module."""

from __future__ import annotations

from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import llm.gap_analysis as gap_analysis  # noqa: E402


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


def test_retrieve_from_vector_store_parses_results():
    class DummyResponses:
        def create(self, **_kwargs):
            return {
                "output": [
                    {
                        "content": [
                            {
                                "type": "file_search_results",
                                "file_search": {
                                    "results": [
                                        {
                                            "content": [
                                                {"text": "First snippet"},
                                                {"text": ""},
                                            ]
                                        },
                                        {"text": "Second snippet"},
                                    ]
                                },
                            }
                        ]
                    }
                ]
            }

    class DummyClient:
        def __init__(self):
            self.responses = DummyResponses()

    result = gap_analysis.retrieve_from_vector_store(
        "query",
        vector_store_id="store-123",
        client=DummyClient(),
        top_k=2,
    )
    assert result == ["First snippet", "Second snippet"]


def test_analyze_vacancy_normalises_esco_and_skips_vector_store(monkeypatch):
    calls: dict[str, object] = {"normalize": None, "retrieve": 0}

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

    class DummyMessages:
        def __init__(self):
            self._response_text = "# Report\n- Item"

        def list(self, **_kwargs):
            return {
                "data": [
                    {
                        "content": [
                            {"text": self._response_text},
                        ]
                    }
                ]
            }

    class DummyRuns:
        def create_and_poll(self, **_kwargs):
            return SimpleNamespace(status="completed", usage={"total_tokens": 12})

    class DummyThreads:
        def __init__(self):
            self.captured_messages = None
            self.messages = DummyMessages()
            self.runs = DummyRuns()

        def create(self, *, messages):
            self.captured_messages = messages
            return SimpleNamespace(id="thread-1")

    class DummyClient:
        def __init__(self):
            self.beta = SimpleNamespace(threads=DummyThreads())

    result = gap_analysis.analyze_vacancy(
        " Vacancy text ",
        job_title="Engineer",
        lang="en",
        vector_store_id="",  # should skip retrieval and not increment counter
        client=DummyClient(),
    )

    assert isinstance(result.content, str)
    assert result.content.startswith("# Report")
    assert result.usage == {"total_tokens": 12}

    assert calls["normalize"] == ([" Skill A ", "Skill B"], "en")
    assert calls["retrieve"] == 0

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

    class DummyMessages:
        def list(self, **_kwargs):
            return {"data": [{"content": [{"text": "## Result"}]}]}

    class DummyRuns:
        def create_and_poll(self, **_kwargs):
            return {"status": "completed", "usage": {}}

    class DummyThreads:
        def __init__(self):
            self.messages = DummyMessages()
            self.runs = DummyRuns()

        def create(self, *, messages):
            assert messages[0]["role"] == "system"
            return {"id": "thread-2"}

    class DummyClient:
        def __init__(self):
            self.beta = SimpleNamespace(threads=DummyThreads())

    result = gap_analysis.analyze_vacancy(
        "Vacancy text",
        job_title="Title",
        lang="de",
        vector_store_id="store-1",
        client=DummyClient(),
    )

    assert result.content == "## Result"


def test_analyze_vacancy_requires_text():
    with pytest.raises(ValueError):
        gap_analysis.analyze_vacancy(" ")
