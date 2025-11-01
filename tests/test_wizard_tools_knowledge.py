from __future__ import annotations

import json

from wizard_tools import knowledge


def test_index_documents_counts_files() -> None:
    payload = json.loads(knowledge.index_documents(["a.pdf", "b.docx"]))

    assert payload == {"indexed": 2}


def test_semantic_search_normalises_query_and_returns_passages() -> None:
    payload = json.loads(knowledge.semantic_search("  talent strategy  ", k=2))

    assert payload["query"] == "talent strategy"
    assert payload["k"] == 2
    assert len(payload["passages"]) == 2
    assert payload["passages"][0]["source"].startswith("doc_")


def test_semantic_search_handles_empty_query() -> None:
    payload = json.loads(knowledge.semantic_search("", k=0))

    assert payload["query"] == ""
    assert payload["k"] == 0
    assert payload["passages"][0]["text"] == "…"


def test_attach_context_roundtrips_payload() -> None:
    passages = [{"text": "Example", "source": "doc_1.md"}]
    payload = json.loads(knowledge.attach_context("stage-1", passages))

    assert payload == {"attached": True, "stage_id": "stage-1", "passages": passages}
