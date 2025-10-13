"""Gap analysis helpers using OpenAI Assistants and ESCO context."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from openai import OpenAIError

from config import VECTOR_STORE_ID, ModelTask, get_model_for
from core.esco_utils import classify_occupation, get_essential_skills, normalize_skills
from openai_utils.api import ChatCallResult, get_client

logger = logging.getLogger("cognitive_needs.gap_analysis")

_ASSISTANT_ID = "asst_xiCpNIMzJnKCtajrLgW0N5ub"
_MAX_VACANCY_CHARS = 4500
_DEFAULT_TOP_K = 4


@dataclass(slots=True)
class GapContext:
    """Container for optional enrichment data."""

    occupation: Mapping[str, Any] | None = None
    essential_skills: Sequence[str] | None = None
    rag_snippets: Sequence[str] | None = None

    def has_esco(self) -> bool:
        return bool(self.occupation or self.essential_skills)

    def esco_block(self, lang: str) -> str:
        if not self.has_esco():
            return ""
        parts: list[str] = []
        if self.occupation:
            label = str(self.occupation.get("preferredLabel") or "").strip()
            group = str(self.occupation.get("group") or "").strip()
            uri = str(self.occupation.get("uri") or "").strip()
            lines = [f"• Bezeichnung: {label}" if lang.startswith("de") else f"• Label: {label}"]
            if group:
                lines.append(f"• Gruppe: {group}" if lang.startswith("de") else f"• Group: {group}")
            if uri:
                lines.append(f"• URI: {uri}")
            parts.append("\n".join(lines))
        skills = [str(skill).strip() for skill in (self.essential_skills or []) if str(skill).strip()]
        if skills:
            header = "• Essenzielle Kompetenzen:" if lang.startswith("de") else "• Essential skills:"
            skill_lines = "\n".join(f"  - {skill}" for skill in skills[:12])
            parts.append("\n".join([header, skill_lines]))
        body = "\n\n".join(filter(None, parts)).strip()
        return f"【ESCO】\n{body}" if body else ""

    def rag_block(self, lang: str) -> str:
        snippets = [str(item).strip() for item in (self.rag_snippets or []) if str(item).strip()]
        if not snippets:
            return ""
        header = "【RAG】\n" + (
            "Top Hinweise aus Wissensbasis:" if lang.startswith("de") else "Top knowledge base snippets:"
        )
        lines = "\n".join(f"- {snippet}" for snippet in snippets[:_DEFAULT_TOP_K])
        return f"{header}\n{lines}".strip()


def retrieve_from_vector_store(
    query: str,
    *,
    vector_store_id: str | None = None,
    top_k: int = _DEFAULT_TOP_K,
    client: Any | None = None,
) -> list[str]:
    """Return text snippets from the configured vector store for ``query``."""

    store_id = (vector_store_id or VECTOR_STORE_ID or "").strip()
    if not store_id or not str(query or "").strip():
        return []

    api = client or get_client()
    try:
        response = api.responses.create(
            model=get_model_for(ModelTask.RAG_SUGGESTIONS),
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": str(query).strip(),
                        }
                    ],
                }
            ],
            tools=[{"type": "file_search", "vector_store_ids": [store_id]}],
            tool_choice={"type": "file_search"},
            max_output_tokens=1,
            metadata={"task": "gap_analysis"},
        )
    except OpenAIError as err:  # pragma: no cover - defensive network guard
        logger.warning("Vector store lookup failed: %s", err)
        return []
    except Exception as err:  # pragma: no cover - defensive
        logger.warning("Unexpected vector store failure: %s", err)
        return []

    results: list[str] = []
    for item in _iter_file_search_results(response):
        text = (item or "").strip()
        if text and text not in results:
            results.append(text)
        if len(results) >= max(1, top_k):
            break
    return results


def _iter_file_search_results(response: Any) -> Iterable[str]:
    output = getattr(response, "output", None)
    if output is None and isinstance(response, Mapping):
        output = response.get("output")
    if not output:
        return []

    snippets: list[str] = []
    for item in output:
        content = getattr(item, "content", None)
        if content is None and isinstance(item, Mapping):
            content = item.get("content")
        if not content:
            continue
        for entry in content:
            entry_type = getattr(entry, "type", None)
            file_search = getattr(entry, "file_search", None)
            if entry_type is None and isinstance(entry, Mapping):
                entry_type = entry.get("type")
                file_search = entry.get("file_search")
            if entry_type != "file_search_results" or not file_search:
                continue
            results = getattr(file_search, "results", None)
            if results is None and isinstance(file_search, Mapping):
                results = file_search.get("results")
            if not results:
                continue
            for result in results:
                text = _extract_result_text(result)
                if text:
                    snippets.append(text)
    return snippets


def _extract_result_text(result: Any) -> str:
    if result is None:
        return ""
    if isinstance(result, Mapping):
        content = result.get("content")
        if isinstance(content, Iterable) and not isinstance(content, (str, bytes)):
            parts: list[str] = []
            for part in content:
                text = getattr(part, "text", None)
                if text is None and isinstance(part, Mapping):
                    text = part.get("text")
                if text:
                    parts.append(str(text))
            joined = "\n".join(parts).strip()
            if joined:
                return joined
        text = result.get("text")
        if text:
            return str(text)
    text_attr = getattr(result, "text", None)
    if text_attr:
        return str(text_attr)
    return ""


def build_gap_prompt(
    *,
    vacancy_text: str,
    lang: str,
    job_title: str | None = None,
    context: GapContext | None = None,
) -> list[dict[str, Any]]:
    """Return assistant messages enforcing the structured gap report."""

    trimmed = vacancy_text.strip()
    if len(trimmed) > _MAX_VACANCY_CHARS:
        trimmed = f"{trimmed[:_MAX_VACANCY_CHARS].rstrip()}\u2026"

    language = (lang or "en").strip().lower() or "en"
    locale = "de" if language.startswith("de") else "en"
    heading_intro = (
        "Erstelle einen kompakten Gap-Report auf Deutsch."
        if locale == "de"
        else "Create a concise gap report in English."
    )
    structure_lines = (
        [
            "1. Vacancy snapshot (2 bullet points)",
            "2. ESCO alignment (occupation + essential skills)",
            "3. Notable gaps or risks",
            "4. Recommended next steps",
        ]
        if locale == "en"
        else [
            "1. Stellenüberblick (2 Stichpunkte)",
            "2. ESCO-Abgleich (Beruf + Kernkompetenzen)",
            "3. Wichtige Lücken/Risiken",
            "4. Empfohlene nächste Schritte",
        ]
    )
    system_prompt = "\n".join(
        [
            "You are a hiring operations co-pilot.",
            heading_intro,
            ("Antwort in Markdown mit Überschriften" if locale == "de" else "Respond in Markdown with headings"),
            "Use the exact numbered section layout:",
            *structure_lines,
            (
                "Halte jede Liste auf maximal 3 Punkte."
                if locale == "de"
                else "Keep each list to at most 3 bullet points."
            ),
        ]
    )

    vacancy_header = "【VACANCY】"
    if job_title:
        vacancy_header += f"\nTitle: {job_title.strip()}"
    vacancy_block = f"{vacancy_header}\n{trimmed}".strip()

    blocks: list[dict[str, str]] = [{"type": "text", "text": vacancy_block}]

    ctx = context or GapContext()
    esco_chunk = ctx.esco_block(locale)
    if esco_chunk:
        blocks.append({"type": "text", "text": esco_chunk})

    rag_chunk = ctx.rag_block(locale)
    if rag_chunk:
        blocks.append({"type": "text", "text": rag_chunk})

    return [
        {"role": "system", "content": [{"type": "text", "text": system_prompt}]},
        {"role": "user", "content": blocks},
    ]


def _build_retrieval_query(job_title: str | None, lang: str) -> str:
    locale = (lang or "en").strip().lower()
    if locale.startswith("de"):
        base = "Fasse die wichtigsten Hiring-Hinweise für diese Stelle zusammen."
    else:
        base = "Summarise the most important hiring guidance for this vacancy."
    if job_title:
        return f"{base} Rolle: {job_title.strip()}"
    return base


def _extract_text_from_messages(payload: Any) -> str:
    if payload is None:
        return ""
    data = getattr(payload, "data", None)
    if data is None and isinstance(payload, Mapping):
        data = payload.get("data")
    if not data:
        return ""
    for message in data:
        content = getattr(message, "content", None)
        if content is None and isinstance(message, Mapping):
            content = message.get("content")
        if not content:
            continue
        for entry in content:
            text = getattr(entry, "text", None)
            if text is None and isinstance(entry, Mapping):
                text = entry.get("text")
            if text:
                return str(text)
    return ""


def analyze_vacancy(
    vacancy_text: str,
    *,
    job_title: str | None = None,
    lang: str = "de",
    vector_store_id: str | None = None,
    client: Any | None = None,
) -> ChatCallResult:
    """Execute the assistant gap analysis workflow and return the reply."""

    text = str(vacancy_text or "").strip()
    if not text:
        raise ValueError("vacancy_text must not be empty")

    locale = (lang or "de").strip().lower()

    occupation = None
    try:
        if job_title:
            occupation = classify_occupation(job_title, lang=locale)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("ESCO occupation lookup failed: %s", exc)
        occupation = None

    essential: Sequence[str] = []
    if occupation and occupation.get("uri"):
        try:
            essential = get_essential_skills(str(occupation.get("uri")), lang=locale)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("ESCO essential skills lookup failed: %s", exc)
            essential = []
    normalised_skills: Sequence[str] = []
    if essential:
        try:
            normalised_skills = normalize_skills(list(essential), lang=locale)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("ESCO skill normalisation failed: %s", exc)
            normalised_skills = essential

    retrieval_query = _build_retrieval_query(job_title, locale)
    snippets: Sequence[str] = []
    effective_store_id = (vector_store_id or VECTOR_STORE_ID or "").strip()
    if effective_store_id:
        try:
            snippets = retrieve_from_vector_store(
                retrieval_query,
                vector_store_id=effective_store_id,
                client=client,
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Vector store helper failed: %s", exc)
            snippets = []

    context = GapContext(
        occupation=occupation,
        essential_skills=normalised_skills,
        rag_snippets=snippets,
    )
    messages = build_gap_prompt(
        vacancy_text=text,
        lang=locale,
        job_title=job_title,
        context=context,
    )

    api = client or get_client()
    thread = api.beta.threads.create(messages=messages)
    run = api.beta.threads.runs.create_and_poll(
        thread_id=getattr(thread, "id", thread.get("id") if isinstance(thread, Mapping) else None),
        assistant_id=_ASSISTANT_ID,
    )
    status = getattr(run, "status", None)
    if status is None and isinstance(run, Mapping):
        status = run.get("status")
    if status and status not in {"completed", "requires_action"}:
        raise RuntimeError(f"Gap analysis run failed: {status}")

    messages_payload = api.beta.threads.messages.list(
        thread_id=getattr(thread, "id", thread.get("id") if isinstance(thread, Mapping) else None),
        order="desc",
        limit=1,
    )
    content = _extract_text_from_messages(messages_payload).strip()
    if not content:
        raise RuntimeError("Assistant returned no content")

    usage = getattr(run, "usage", None)
    if usage is None and isinstance(run, Mapping):
        usage = run.get("usage")
    usage_dict = usage if isinstance(usage, Mapping) else {}

    return ChatCallResult(content=content, tool_calls=[], usage=dict(usage_dict))
