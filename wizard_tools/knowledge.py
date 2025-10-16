"""Knowledge and retrieval helper tools."""

from __future__ import annotations

import json
from typing import Dict, List

from agents import function_tool


@function_tool
def index_documents(files: List[str]) -> str:
    """Add files to vector store for File Search."""

    return json.dumps({"indexed": len(files)})


@function_tool
def semantic_search(query: str, k: int = 5) -> str:
    """Search vector store."""

    return json.dumps({"passages": [{"text": "…", "source": "doc1.pdf"}]})


@function_tool
def attach_context(stage_id: str, passages: List[Dict[str, str]]) -> str:
    """Associate retrieved passages with a stage."""

    return json.dumps({"attached": True, "stage_id": stage_id})


__all__ = ["attach_context", "index_documents", "semantic_search"]

