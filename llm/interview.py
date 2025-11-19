"""Interview guide generation via the OpenAI Responses API."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from config import ModelTask, REASONING_EFFORT, get_model_for
from llm.openai_responses import build_json_schema_format, call_responses
from models.interview_guide import (
    InterviewGuide,
    InterviewGuideFocusArea,
    InterviewGuideMetadata,
    InterviewGuideQuestion,
)
from prompts import prompt_registry
from utils.i18n import tr

logger = logging.getLogger(__name__)

__all__ = ["InterviewGuideResult", "generate_interview_guide"]


@dataclass(slots=True)
class InterviewGuideResult:
    """Container describing the generated guide and whether a fallback was used."""

    guide: InterviewGuide
    used_fallback: bool
    error_detail: str | None = None


def _resolve_language(lang: str | None) -> str:
    return "de" if str(lang or "de").lower().startswith("de") else "en"


def _normalise_items(payload: Sequence[str] | str) -> list[str]:
    if isinstance(payload, str):
        items = [part.strip() for part in payload.replace("\r", "").splitlines()]
    else:
        items = [str(item).strip() for item in payload]
    return [item for item in items if item]


def _sentence_case(text: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        return cleaned
    return cleaned[0].upper() + cleaned[1:]


def _build_fallback_guide(
    *,
    job_title: str,
    responsibilities: list[str],
    hard_skills: list[str],
    soft_skills: list[str],
    audience: str,
    num_questions: int,
    lang: str,
    culture_note: str,
    tone_text: str,
) -> InterviewGuide:
    """Return a deterministic interview guide as a fallback template."""

    lang_code = _resolve_language(lang)

    def _tr(value_de: str, value_en: str) -> str:
        return tr(value_de, value_en, lang=lang_code)

    audience_display = {
        "general": _tr("Allgemeines Interviewteam", "General interview panel"),
        "technical": _tr("Technisches Interviewteam", "Technical panel"),
        "leadership": _tr("Führungsteam", "Leadership panel"),
    }.get(audience, audience)

    job_title_text = job_title.strip() or _tr("diese Position", "this role")

    def _make_question(question: str, focus: str, evaluation: str) -> InterviewGuideQuestion:
        return InterviewGuideQuestion(
            question=_sentence_case(question),
            focus=focus.strip(),
            evaluation=evaluation.strip(),
        )

    questions: list[InterviewGuideQuestion] = []

    def _add_question(entry: InterviewGuideQuestion) -> None:
        max_questions = max(3, min(10, num_questions))
        if len(questions) >= max_questions:
            return
        key = entry.question.strip().lower()
        if key in {existing.question.strip().lower() for existing in questions}:
            return
        questions.append(entry)

    motivation_question = _make_question(
        _tr(
            f"Was motiviert Sie an der Rolle als {job_title_text}?",
            f"What excites you most about the {job_title_text} opportunity?",
        ),
        _tr("Motivation & Passung", "Motivation & fit"),
        _tr(
            "Suchen Sie nach konkreten Beweggründen, Bezug zum Team und Erwartungen an die Rolle.",
            "Listen for concrete reasons, links to the team and expectations for the role.",
        ),
    )
    _add_question(motivation_question)

    if culture_note:
        culture_question = _make_question(
            _tr(
                "Welche Aspekte unserer beschriebenen Kultur sprechen Sie besonders an und wie würden Sie sie im Alltag leben?",
                "Which aspects of the culture we described resonate with you and how would you live them day to day?",
            ),
            _tr("Kulturelle Passung", "Cultural alignment"),
            _tr(
                "Hören Sie auf Beispiele aus der Vergangenheit und darauf, wie Werte in konkretes Verhalten übersetzt werden.",
                "Listen for past examples and how values translate into concrete behaviour.",
            ),
        )
        _add_question(culture_question)

    for item in responsibilities[:3]:
        _add_question(
            _make_question(
                _tr(
                    f"Beschreiben Sie ein Projekt, in dem Sie '{item}' verantwortet haben. Wie sind Sie vorgegangen und welches Ergebnis wurde erreicht?",
                    f"Describe a project where you were responsible for '{item}'. How did you approach it and what was the outcome?",
                ),
                _tr("Umsetzung zentraler Aufgaben", "Executing key responsibilities"),
                _tr(
                    "Achten Sie auf Struktur, Prioritätensetzung und darauf, welchen Beitrag die Kandidat:in geleistet hat.",
                    "Look for structure, prioritisation and the candidate's personal contribution.",
                ),
            )
        )

    for skill in hard_skills[:4]:
        _add_question(
            _make_question(
                _tr(
                    f"Wie gehen Sie bei {skill} vor? Beschreiben Sie einen konkreten Anwendungsfall.",
                    f"How do you approach {skill}? Walk us through a specific use case.",
                ),
                _tr("Technische Tiefe", "Technical depth"),
                _tr(
                    "Erfragen Sie Details zu Methodik, Tools und Ergebnissen, um die tatsächliche Expertise zu bewerten.",
                    "Probe for methodology, tools and measurable outcomes to judge depth of expertise.",
                ),
            )
        )

    for skill in soft_skills[:3]:
        _add_question(
            _make_question(
                _tr(
                    f"Erzählen Sie von einer Situation, in der '{skill}' besonders wichtig war. Wie haben Sie reagiert?",
                    f"Tell me about a time when '{skill}' was critical. How did you respond?",
                ),
                _tr("Verhaltenskompetenzen", "Behavioural competencies"),
                _tr(
                    "Suchen Sie nach konkreten Beispielen, Selbstreflexion und Auswirkungen auf das Umfeld.",
                    "Look for concrete examples, self-reflection and the impact on others.",
                ),
            )
        )

    fallback_questions = [
        _make_question(
            _tr(
                "Wie sichern Sie eine gute Zusammenarbeit im Team?",
                "How do you ensure smooth collaboration across the team?",
            ),
            _tr("Teamarbeit", "Collaboration"),
            _tr(
                "Hören Sie auf Kommunikationsstil, Konfliktlösung und konkrete Beispiele erfolgreicher Zusammenarbeit.",
                "Probe for communication style, conflict resolution and concrete collaboration examples.",
            ),
        ),
        _make_question(
            _tr(
                "Wie planen Sie Ihre ersten 90 Tage in einer neuen Rolle?",
                "How would you structure your first 90 days in this role?",
            ),
            _tr("Onboarding & Struktur", "Onboarding & structure"),
            _tr(
                "Achten Sie auf klare Prioritäten, Stakeholder-Management und Lernziele.",
                "Look for clear priorities, stakeholder management and learning goals.",
            ),
        ),
        _make_question(
            _tr(
                "Welche offene Frage haben Sie an uns?",
                "What open questions do you have for us?",
            ),
            _tr("Bidirektionaler Austausch", "Bidirectional exchange"),
            _tr(
                "Gute Kandidat:innen nutzen die Chance, offene Themen strukturiert anzusprechen.",
                "Strong candidates use the opportunity to address open topics in a structured way.",
            ),
        ),
    ]

    for question in fallback_questions:
        _add_question(question)

    if len(questions) < num_questions:
        additional_sources = responsibilities[3:] + hard_skills[4:] + soft_skills[3:]
        for item in additional_sources:
            _add_question(
                _make_question(
                    _tr(
                        f"Welche Erfahrungen haben Sie mit '{item}' gesammelt und was haben Sie daraus gelernt?",
                        f"What experience do you have with '{item}' and what did you learn from it?",
                    ),
                    _tr("Vertiefung", "Deep dive"),
                    _tr(
                        "Fragen Sie nach Ergebnissen, Lessons Learned und der Übertragbarkeit auf die Rolle.",
                        "Ask about outcomes, lessons learned and applicability to the role.",
                    ),
                )
            )
            if len(questions) >= num_questions:
                break

    if len(questions) > num_questions:
        questions = questions[:num_questions]

    focus_areas: list[InterviewGuideFocusArea] = []
    if responsibilities:
        focus_areas.append(
            InterviewGuideFocusArea(
                label=_tr("Schlüsselaufgaben", "Key responsibilities"),
                items=responsibilities[:5],
            )
        )
    if hard_skills:
        focus_areas.append(
            InterviewGuideFocusArea(
                label=_tr("Pflicht-Skills (fachlich)", "Required skills (technical)"),
                items=hard_skills[:5],
            )
        )
    if soft_skills:
        focus_areas.append(
            InterviewGuideFocusArea(
                label=_tr("Pflicht-Skills (Zusammenarbeit)", "Required skills (collaboration)"),
                items=soft_skills[:5],
            )
        )

    evaluation_notes = [
        _tr(
            "Bewerte Klarheit und Struktur der Antworten. Fordere Nachfragen, wenn Beispiele fehlen.",
            "Assess clarity and structure of answers. Ask follow-ups when examples are missing.",
        ),
        _tr(
            "Bitte um konkrete Resultate, Kennzahlen oder Lernerfahrungen, um Impact zu verifizieren.",
            "Request concrete outcomes, metrics, or learnings to verify impact.",
        ),
        _tr(
            "Vergleiche Antworten mit dem gewünschten Ton und Kulturfit der Organisation.",
            "Check answers against the desired tone and cultural fit of the organisation.",
        ),
    ]
    if culture_note:
        evaluation_notes.append(
            _tr(
                "Achte besonders auf Hinweise zur beschriebenen Unternehmenskultur.",
                "Pay special attention to alignment with the described company culture.",
            )
        )

    metadata = InterviewGuideMetadata(
        language=lang_code,
        heading=(_tr("Interviewleitfaden", "Interview Guide") + f" – {job_title_text}"),
        job_title=job_title_text,
        audience=audience,
        audience_label=audience_display,
        tone=tone_text,
        culture_note=culture_note or None,
    )

    guide = InterviewGuide(
        metadata=metadata,
        focus_areas=focus_areas,
        questions=questions,
        evaluation_notes=evaluation_notes,
    )
    return guide.ensure_markdown()


def _prepare_payload(
    *,
    job_title: str,
    responsibilities: Sequence[str] | str,
    hard_skills: Sequence[str] | str,
    soft_skills: Sequence[str] | str,
    audience: str,
    num_questions: int,
    lang: str,
    company_culture: str,
    tone: str | None,
) -> tuple[dict[str, Any], InterviewGuide]:
    responsibilities_list = _normalise_items(responsibilities)
    hard_list = _normalise_items(hard_skills)
    soft_list = _normalise_items(soft_skills)

    lang_code = _resolve_language(lang)
    tone_text = str(tone or "").strip()
    if not tone_text:
        tone_text = tr(
            "professionell und strukturiert",
            "professional and structured",
            lang=lang_code,
        )

    culture_note = company_culture.strip()

    fallback = _build_fallback_guide(
        job_title=job_title,
        responsibilities=responsibilities_list,
        hard_skills=hard_list,
        soft_skills=soft_list,
        audience=audience,
        num_questions=num_questions,
        lang=lang_code,
        culture_note=culture_note,
        tone_text=tone_text,
    )

    payload: dict[str, Any] = {
        "language": lang_code,
        "job_title": job_title,
        "requested_questions": max(3, min(10, num_questions)),
        "audience": audience,
        "audience_display": fallback.metadata.audience_label,
        "tone": tone_text,
        "company_culture": culture_note,
        "responsibilities": responsibilities_list,
        "hard_skills": hard_list,
        "soft_skills": soft_list,
        "seed_focus_areas": [area.model_dump() for area in fallback.focus_areas],
        "sample_questions": [question.model_dump() for question in fallback.questions[: max(3, min(6, num_questions))]],
        "evaluation_note_examples": list(fallback.evaluation_notes),
    }

    return payload, fallback


def _build_messages(payload: Mapping[str, Any]) -> list[dict[str, str]]:
    lang = str(payload.get("language") or "de").lower()
    system_default = prompt_registry.get("llm.interview_guide.system", locale="en")
    system_msg = prompt_registry.get(
        "llm.interview_guide.system",
        locale=lang,
        default=system_default,
    )
    instruction_templates = prompt_registry.get("llm.interview_guide.instructions", locale=lang)
    instruction_lines = [str(template) for template in instruction_templates]
    context_json = json.dumps(payload, ensure_ascii=False, indent=2)
    user_message = "\n".join(instruction_lines) + "\n\nContext:\n```json\n" + context_json + "\n```"
    return [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_message},
    ]


def generate_interview_guide(
    *,
    job_title: str,
    responsibilities: Sequence[str] | str = (),
    hard_skills: Sequence[str] | str = (),
    soft_skills: Sequence[str] | str = (),
    audience: str = "general",
    num_questions: int = 5,
    lang: str = "de",
    company_culture: str = "",
    tone: str | None = None,
    model: str | None = None,
) -> InterviewGuideResult:
    """Generate an interview guide tailored to the provided context."""

    payload, fallback = _prepare_payload(
        job_title=job_title,
        responsibilities=responsibilities,
        hard_skills=hard_skills,
        soft_skills=soft_skills,
        audience=audience,
        num_questions=num_questions,
        lang=lang,
        company_culture=company_culture,
        tone=tone,
    )

    if model is None:
        model = get_model_for(ModelTask.INTERVIEW_GUIDE)

    messages = _build_messages(payload)
    schema = InterviewGuide.model_json_schema()

    try:
        response = call_responses(
            messages,
            model=model,
            response_format=build_json_schema_format(
                name="interviewGuide",
                schema=schema,
            ),
            temperature=0.6,
            max_completion_tokens=900,
            reasoning_effort=REASONING_EFFORT,
            task=ModelTask.INTERVIEW_GUIDE,
        )
        data = json.loads(response.content or "{}")
        guide = InterviewGuide.model_validate(data).ensure_markdown()
        return InterviewGuideResult(guide=guide, used_fallback=False)
    except Exception as exc:  # pragma: no cover - defensive fallback
        error_detail = f"{type(exc).__name__}: {exc}".strip()
        logger.exception("Interview guide generation failed; using deterministic fallback.")
        fallback_with_markdown = fallback.ensure_markdown()
        return InterviewGuideResult(
            guide=fallback_with_markdown,
            used_fallback=True,
            error_detail=error_detail,
        )
