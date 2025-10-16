"""Gap analysis helpers using OpenAI Assistants and ESCO context."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from config import VECTOR_STORE_ID, ModelTask, get_model_for
from core.esco_utils import classify_occupation, get_essential_skills, normalize_skills
from openai_utils.api import ChatCallResult, call_chat_api
from openai_utils.tools import build_file_search_tool

logger = logging.getLogger("cognitive_needs.gap_analysis")

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

    if client is not None:  # pragma: no cover - backwards compatibility shim
        logger.debug("Custom OpenAI client overrides are ignored by call_chat_api")

    try:
        result = call_chat_api(
            [
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
            model=get_model_for(ModelTask.RAG_SUGGESTIONS),
            tools=[build_file_search_tool(store_id)],
            tool_choice={"type": "file_search"},
            max_tokens=1,
            extra={"metadata": {"task": "gap_analysis"}},
            task=ModelTask.RAG_SUGGESTIONS,
            capture_file_search=True,
        )
    except RuntimeError as err:  # pragma: no cover - defensive network guard
        logger.warning("Vector store lookup failed: %s", err)
        return []
    except Exception as err:  # pragma: no cover - defensive
        logger.warning("Unexpected vector store failure: %s", err)
        return []

    snippets: list[str] = []
    for entry in result.file_search_results or []:
        text = str(entry.get("text") or "").strip()
        if text and text not in snippets:
            snippets.append(text)
        if len(snippets) >= max(1, top_k):
            break
    return snippets


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
            "You are a hiring operations co-pilot. Silently plan how you will build the report—do not output the plan. Execute your plan step by step and do not stop until the user's needs are fully met.",
            heading_intro,
            ("Antwort in Markdown mit Überschriften" if locale == "de" else "Respond in Markdown with headings"),
            (
                "Folge strikt diesen Schritten: 1) Kontext erfassen, 2) Struktur zuweisen, 3) Inhalte verfassen, 4) Vollständigkeit prüfen."
                if locale == "de"
                else "Follow these steps strictly: 1) Absorb context, 2) map content to each section, 3) write the sections, 4) verify completeness."
            ),
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

    tools: list[dict[str, Any]] = []
    tool_choice: str | None = None
    if effective_store_id:
        tools.append(build_file_search_tool(effective_store_id))
        tool_choice = "auto"

    result = call_chat_api(
        messages,
        model=get_model_for(ModelTask.EXPLANATION),
        tools=tools or None,
        tool_choice=tool_choice,
        extra={"metadata": {"task": "gap_analysis"}},
        task=ModelTask.EXPLANATION,
    )

    if not (result.content or "").strip():
        raise RuntimeError("Assistant returned no content")

    return result
