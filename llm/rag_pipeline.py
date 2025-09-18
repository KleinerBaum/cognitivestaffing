"""Field-aware retrieval helpers for the structured extraction pipeline."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, MutableMapping, Sequence

from config import VECTOR_STORE_ID, ModelTask, get_model_for
from openai import OpenAIError

from openai_utils import get_client


logger = logging.getLogger("cognitive_needs.rag")


@dataclass(slots=True)
class FieldSpec:
    """Specification for retrieving context for a schema field."""

    field: str
    instruction: str


@dataclass(slots=True)
class RetrievedChunk:
    """Container for a retrieved or fallback text chunk."""

    text: str
    score: float
    source_id: str | None = None
    file_id: str | None = None
    chunk_id: str | None = None
    is_fallback: bool = False
    metadata: MutableMapping[str, Any] | None = field(default=None, repr=False)

    def to_payload(self, *, max_chars: int = 1200) -> dict[str, Any]:
        """Return a serialisable representation for prompts/metadata."""

        text = self.text.strip()
        if max_chars > 0 and len(text) > max_chars:
            text = text[: max_chars - 1].rstrip() + "\u2026"
        payload = {
            "text": text,
            "score": float(self.score),
            "source_id": self.source_id,
            "file_id": self.file_id,
            "chunk_id": self.chunk_id,
            "fallback": self.is_fallback,
        }
        if self.metadata:
            payload["metadata"] = dict(self.metadata)
        return payload


@dataclass(slots=True)
class FieldExtractionContext:
    """Collected context for a target field."""

    field: str
    instruction: str
    chunks: list[RetrievedChunk]

    def select_chunk(self, value: Any) -> RetrievedChunk | None:
        """Return the chunk that best matches ``value``.

        Selection favours non-fallback snippets whose text contains the
        extracted value (case-insensitive). When no direct match exists, the
        highest scoring chunk returned by the vector store is used. If no
        chunks are available, ``None`` is returned.
        """

        if not self.chunks:
            return None

        candidates = list(self.chunks)
        tokens = _value_tokens(value)
        best: RetrievedChunk | None = None
        best_score = float("-inf")
        for chunk in candidates:
            score = float(chunk.score)
            if chunk.is_fallback:
                score -= 0.35
            match_bonus = _match_bonus(chunk.text, tokens)
            score += match_bonus
            if score > best_score:
                best_score = score
                best = chunk
        if best is None:
            return max(candidates, key=lambda c: (float(c.score), not c.is_fallback))
        return best

    def to_metadata(self) -> dict[str, Any]:
        """Return a serialisable structure for metadata storage."""

        return {
            "instruction": self.instruction,
            "chunks": [chunk.to_payload() for chunk in self.chunks],
        }


class RAGPipeline:
    """Retrieve per-field context snippets from an OpenAI vector store."""

    def __init__(
        self,
        *,
        vector_store_id: str | None = None,
        base_text: str = "",
        top_k: int = 4,
        model: str | None = None,
        fallback_chars: int = 420,
    ) -> None:
        self.vector_store_id = (vector_store_id or VECTOR_STORE_ID or "").strip()
        self.base_text = base_text
        self.top_k = max(1, top_k)
        self.model = model or get_model_for(ModelTask.EXTRACTION)
        self.fallback_chars = max(120, fallback_chars)
        self._fallback_offset = 0
        self._client = None

    def _client_instance(self):
        if self._client is None:
            self._client = get_client()
        return self._client

    def _build_query(self, spec: FieldSpec) -> str:
        return (
            "Identify the most relevant passages for the following vacancy field. "
            "Return concise snippets only: "
            f"{spec.field}. Instruction: {spec.instruction}"
        )

    def _collect_results(self, response: Any) -> list[RetrievedChunk]:
        output = getattr(response, "output", None)
        if output is None and isinstance(response, Mapping):
            output = response.get("output")
        chunks: list[RetrievedChunk] = []
        if not output:
            return chunks
        for item in output:
            if item is None:
                continue
            if isinstance(item, Mapping):
                content = item.get("content")
            else:
                content = getattr(item, "content", None)
            if not content:
                continue
            for entry in content:
                if entry is None:
                    continue
                if isinstance(entry, Mapping):
                    entry_type = entry.get("type")
                    file_search = entry.get("file_search")
                else:
                    entry_type = getattr(entry, "type", None)
                    file_search = getattr(entry, "file_search", None)
                if entry_type != "file_search_results" or not file_search:
                    continue
                results = (
                    file_search.get("results")
                    if isinstance(file_search, Mapping)
                    else None
                )
                if not results:
                    continue
                for res in results:
                    if res is None or not isinstance(res, Mapping):
                        continue
                    text = _result_text(res)
                    if not text:
                        continue
                    score = _safe_float(res.get("score", 0.0))
                    file_id = res.get("file_id")
                    chunk_id = res.get("chunk_id") or res.get("id")
                    metadata = (
                        res.get("metadata")
                        if isinstance(res.get("metadata"), Mapping)
                        else None
                    )
                    source = None
                    if metadata:
                        source = metadata.get("source") or metadata.get("filename")
                    source = source or file_id or chunk_id
                    chunks.append(
                        RetrievedChunk(
                            text=text,
                            score=score,
                            source_id=str(source) if source else None,
                            file_id=file_id,
                            chunk_id=chunk_id,
                            metadata=dict(metadata) if metadata else None,
                        )
                    )
        chunks.sort(key=lambda c: c.score, reverse=True)
        if len(chunks) > self.top_k:
            return chunks[: self.top_k]
        return chunks

    def _next_fallback(self) -> RetrievedChunk | None:
        if not self.base_text:
            return None
        length = len(self.base_text)
        if length == 0:
            return None
        start = self._fallback_offset
        end = min(length, start + self.fallback_chars)
        snippet = self.base_text[start:end].strip()
        if not snippet:
            if start == 0:
                return None
            self._fallback_offset = 0
            return self._next_fallback()
        self._fallback_offset = end if end < length else 0
        return RetrievedChunk(
            text=snippet,
            score=0.0,
            source_id=f"fallback:{start}-{end}",
            is_fallback=True,
        )

    def _retrieve_for(self, spec: FieldSpec) -> list[RetrievedChunk]:
        if not self.vector_store_id:
            fallback = self._next_fallback()
            return [fallback] if fallback else []
        query = self._build_query(spec)
        try:
            response = self._client_instance().responses.create(
                model=self.model,
                input=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": query,
                            }
                        ],
                    }
                ],
                tools=[
                    {"type": "file_search", "vector_store_ids": [self.vector_store_id]}
                ],
                tool_choice={"type": "file_search"},
                max_output_tokens=1,
                metadata={"field": spec.field},
            )
        except OpenAIError as err:  # pragma: no cover - defensive
            logger.warning("Vector store lookup failed for %s: %s", spec.field, err)
            fallback = self._next_fallback()
            return [fallback] if fallback else []
        except Exception as err:  # pragma: no cover - defensive
            logger.warning("Vector store lookup failed for %s: %s", spec.field, err)
            fallback = self._next_fallback()
            return [fallback] if fallback else []

        chunks = self._collect_results(response)
        if chunks:
            return chunks
        fallback = self._next_fallback()
        return [fallback] if fallback else []

    def run(self, specs: Sequence[FieldSpec]) -> dict[str, FieldExtractionContext]:
        contexts: dict[str, FieldExtractionContext] = {}
        for spec in specs:
            chunks = self._retrieve_for(spec)
            contexts[spec.field] = FieldExtractionContext(
                field=spec.field,
                instruction=spec.instruction,
                chunks=chunks,
            )
        return contexts


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _result_text(result: Mapping[str, Any]) -> str:
    content = result.get("content")
    if isinstance(content, Iterable):
        parts: list[str] = []
        for part in content:
            if part is None:
                continue
            if isinstance(part, Mapping):
                text = part.get("text")
            else:
                text = getattr(part, "text", None)
            if text:
                parts.append(str(text))
        joined = "\n".join(parts).strip()
        if joined:
            return joined
    text = result.get("text")
    if text:
        return str(text)
    return ""


def _collect_schema_fields(schema: Mapping[str, Any], prefix: str = "") -> list[str]:
    props = schema.get("properties")
    if not isinstance(props, Mapping):
        return []
    fields: list[str] = []
    for key, definition in props.items():
        path = f"{prefix}{key}"
        if isinstance(definition, Mapping) and (
            definition.get("type") == "object"
            or isinstance(definition.get("properties"), Mapping)
        ):
            fields.extend(_collect_schema_fields(definition, f"{path}."))
        else:
            fields.append(path)
    return fields


def _default_instruction(field_name: str) -> str:
    from core.schema import BOOL_FIELDS, LIST_FIELDS

    label = field_name.replace("_", " ")
    if field_name in BOOL_FIELDS:
        return f"Decide whether '{label}' is mentioned (return true or false)."
    if field_name in LIST_FIELDS:
        return f"List each distinct item for '{label}'."
    return f"Extract the most precise value for '{label}'."


def build_field_queries(schema: Mapping[str, Any] | None = None) -> list[FieldSpec]:
    """Return field specifications based on the provided schema."""

    if schema:
        fields = _collect_schema_fields(schema)
    else:
        from llm.prompts import FIELDS_ORDER

        fields = list(FIELDS_ORDER)
    return [FieldSpec(field=f, instruction=_default_instruction(f)) for f in fields]


def collect_field_contexts(
    specs: Sequence[FieldSpec],
    *,
    vector_store_id: str | None = None,
    base_text: str = "",
    top_k: int = 4,
    model: str | None = None,
) -> dict[str, FieldExtractionContext]:
    """Retrieve field contexts using :class:`RAGPipeline`."""

    pipeline = RAGPipeline(
        vector_store_id=vector_store_id,
        base_text=base_text,
        top_k=top_k,
        model=model,
    )
    return pipeline.run(specs)


def build_global_context(
    text: str,
    *,
    max_chunks: int = 3,
    chunk_chars: int = 500,
) -> list[RetrievedChunk]:
    """Return coarse global context chunks from ``text`` for the extractor."""

    clean_lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not clean_lines:
        clean_lines = [text.strip()] if text.strip() else []
    chunks: list[RetrievedChunk] = []
    buffer = ""
    start_idx = 0
    cursor = 0
    for line in clean_lines:
        if not buffer:
            start_idx = cursor
        tentative = f"{buffer} {line}".strip()
        if len(tentative) <= chunk_chars:
            buffer = tentative
        else:
            if buffer:
                end_idx = cursor
                chunks.append(
                    RetrievedChunk(
                        text=buffer,
                        score=0.0,
                        source_id=f"global:{start_idx}-{end_idx}",
                        is_fallback=True,
                    )
                )
                if len(chunks) >= max_chunks:
                    return chunks
            buffer = line
            start_idx = cursor
        cursor += len(line) + 1
    if buffer and len(chunks) < max_chunks:
        chunks.append(
            RetrievedChunk(
                text=buffer,
                score=0.0,
                source_id=f"global:{start_idx}-{cursor}",
                is_fallback=True,
            )
        )
    return chunks[:max_chunks]


def _value_tokens(value: Any) -> list[str]:
    """Return significant tokens for ``value`` used in chunk selection."""

    tokens: list[str] = []
    if value is None:
        return tokens
    if isinstance(value, str):
        clean = value.strip()
        if clean:
            tokens.append(clean.casefold())
        return tokens
    if isinstance(value, Mapping):
        for item in value.values():
            tokens.extend(_value_tokens(item))
        return tokens
    if isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray)):
        for item in value:
            tokens.extend(_value_tokens(item))
        return tokens
    text = str(value).strip()
    if text:
        tokens.append(text.casefold())
    return tokens


def _match_bonus(text: str, tokens: Sequence[str]) -> float:
    """Return a score bonus based on ``tokens`` appearing in ``text``."""

    if not tokens:
        return 0.0
    lowered = text.casefold()
    bonus = 0.0
    for token in tokens:
        if len(token) < 3:
            continue
        if token in lowered:
            bonus += 0.75
    return bonus


__all__ = [
    "FieldSpec",
    "RetrievedChunk",
    "FieldExtractionContext",
    "RAGPipeline",
    "build_field_queries",
    "collect_field_contexts",
    "build_global_context",
]
