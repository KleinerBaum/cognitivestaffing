"""Tests for the RAG retrieval pipeline and extraction integration."""

from __future__ import annotations

import json
import types
from typing import Any

import pytest

from llm.rag_pipeline import (
    FieldExtractionContext,
    FieldSpec,
    RAGPipeline,
    RetrievedChunk,
    collect_field_contexts,
)
from openai_utils import ChatCallResult
from openai_utils.extraction import extract_with_function


class _DummyResponses:
    """Minimal stub mimicking ``OpenAI.responses`` for tests."""

    def __init__(self, payload: list[dict[str, Any]]) -> None:
        self._payload = payload
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return types.SimpleNamespace(output=self._payload)


def _vector_result(text: str, score: float = 0.9) -> dict[str, Any]:
    return {
        "type": "file_search_results",
        "file_search": {
            "results": [
                {
                    "content": [{"text": text}],
                    "score": score,
                    "file_id": "file-1",
                    "id": "chunk-1",
                    "metadata": {"source": "doc.md"},
                }
            ]
        },
    }


def _empty_vector_payload() -> list[dict[str, Any]]:
    return [
        {
            "content": [
                {
                    "type": "file_search_results",
                    "file_search": {"results": []},
                }
            ]
        }
    ]


def _payload_with_result(text: str, score: float = 0.9) -> list[dict[str, Any]]:
    return [{"content": [_vector_result(text, score=score)]}]


def test_collect_field_contexts_uses_vector_store(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vector store snippets should populate the field context."""

    responses = _DummyResponses(_payload_with_result("Title: Engineer", 0.88))
    monkeypatch.setattr(
        "llm.rag_pipeline.get_client",
        lambda: types.SimpleNamespace(responses=responses),
    )

    spec = FieldSpec(field="position.job_title", instruction="Extract title")
    contexts = collect_field_contexts(
        [spec],
        vector_store_id="vs123",
        base_text="Fallback text",
        top_k=2,
    )

    ctx = contexts["position.job_title"]
    assert len(ctx.chunks) == 1
    chunk = ctx.chunks[0]
    assert chunk.text.startswith("Title: Engineer")
    assert chunk.score == pytest.approx(0.88)
    assert chunk.source_id == "doc.md"
    assert not chunk.is_fallback


def test_collect_field_contexts_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fallback snippets should be returned when no vector hits are available."""

    responses = _DummyResponses(_empty_vector_payload())
    monkeypatch.setattr(
        "llm.rag_pipeline.get_client",
        lambda: types.SimpleNamespace(responses=responses),
    )

    spec = FieldSpec(field="company.name", instruction="Find company")
    pipeline = RAGPipeline(
        vector_store_id="vs123",
        base_text="Acme Corp builds rockets. Second paragraph here.",
        top_k=2,
    )
    contexts = pipeline.run([spec])
    ctx = contexts["company.name"]
    assert len(ctx.chunks) == 1
    chunk = ctx.chunks[0]
    assert chunk.is_fallback
    assert chunk.source_id is not None
    assert chunk.source_id.startswith("fallback:")
    assert "Acme Corp" in chunk.text


def test_field_context_select_chunk_prefers_matching_value() -> None:
    """Chunk selection should favour snippets containing the extracted value."""

    ctx = FieldExtractionContext(
        field="compensation.salary_min",
        instruction="Extract salary",
        chunks=[
            RetrievedChunk(text="Overview paragraph", score=0.9, source_id="doc1"),
            RetrievedChunk(text="Salary is 50000 EUR", score=0.4, source_id="doc2"),
        ],
    )

    selected = ctx.select_chunk(50000)
    assert selected is not None
    assert selected.source_id == "doc2"


def test_extract_with_function_uses_rag_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Extraction should receive only the selected field snippets."""

    captured: dict[str, Any] = {}

    def fake_call(messages, **kwargs):
        captured["messages"] = messages
        return ChatCallResult(
            content=None,
            tool_calls=[
                {
                    "function": {
                        "arguments": json.dumps({"position": {"job_title": "Engineer"}})
                    }
                }
            ],
            usage={},
        )

    monkeypatch.setattr("openai_utils.extraction.api.call_chat_api", fake_call)
    monkeypatch.setattr(
        "openai_utils.extraction.build_extraction_tool", lambda *a, **k: []
    )
    monkeypatch.setattr(
        "core.schema.coerce_and_fill",
        lambda raw: types.SimpleNamespace(model_dump=lambda: raw),
    )

    chunk = RetrievedChunk(text="Title: Engineer", score=0.92, source_id="doc42")
    field_ctx = FieldExtractionContext(
        field="position.job_title",
        instruction="Return the main job title",
        chunks=[chunk],
    )
    global_ctx = [
        RetrievedChunk(
            text="General role summary",
            score=0.0,
            source_id="global",
            is_fallback=True,
        )
    ]

    result = extract_with_function(
        "Full job description text that should be truncated.",
        {
            "type": "object",
            "properties": {
                "position": {
                    "type": "object",
                    "properties": {"job_title": {"type": "string"}},
                }
            },
        },
        model="gpt-test",
        field_contexts={"position.job_title": field_ctx},
        global_context=global_ctx,
    )

    assert result.data["position"]["job_title"] == "Engineer"
    assert "Full job description" not in captured["messages"][1]["content"]
    payload = json.loads(captured["messages"][1]["content"])
    assert payload["fields"][0]["field"] == "position.job_title"
    assert payload["fields"][0]["context"][0]["text"] == "Title: Engineer"
    assert payload["global_context"][0]["fallback"] is True
