"""Prompt templates for LLM interactions."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from core.schema import ALL_FIELDS
from utils.i18n import tr

# ----------------------------------------------------------------------------
# Field enumeration
# ----------------------------------------------------------------------------

# Export schema order for prompt rendering
FIELDS_ORDER: list[str] = ALL_FIELDS


def render_field_bullets() -> str:
    """Return fields as a bullet list in schema order."""
    return "\n".join(f"- {field}" for field in FIELDS_ORDER)


# ----------------------------------------------------------------------------
# Extraction templates
# ----------------------------------------------------------------------------

SYSTEM_JSON_EXTRACTOR: str = (
    "You are an extractor. Return ONLY a JSON object with the exact keys provided. "
    "Use empty strings for missing values and empty lists for missing arrays. No prose. "
    "Provide the main job title without gender markers in position.job_title, the company's legal name in company.name, and the primary city in location.primary_city. "
    "Map common terms: 'Vollzeit' or 'Full-time' -> employment.job_type='full_time', 'Teilzeit' -> 'part_time', "
    "'Festanstellung' or 'Permanent' -> employment.contract_type='permanent', 'Befristet' or 'Fixed term' -> employment.contract_type='fixed_term'. "
    "Detect work policy keywords like 'Remote', 'Home-Office', or 'Hybrid' and map them to employment.work_policy. "
    "If office days per week or remote percentages are mentioned, estimate employment.remote_percentage using a 5-day work week. "
    "Extract salary ranges like '65.000–85.000 €' into numeric compensation.salary_min and compensation.salary_max and set compensation.currency to an ISO code (e.g. EUR). "
    "If variable pay or bonuses such as '10% Variable' are mentioned, set compensation.variable_pay=true and capture the percentage in compensation.bonus_percentage. "
    "List every benefit/perk separately in compensation.benefits as a JSON array of strings. "
    "Collect each key task or responsibility (especially bullet points) in responsibilities.items as a JSON array of strings. "
    "Separate technical vs. social skills: place mandatory hard skills in requirements.hard_skills_required and optional ones in requirements.hard_skills_optional. "
    "Soft skills like communication or teamwork go into requirements.soft_skills_required or requirements.soft_skills_optional depending on whether they are required or marked as nice-to-have. "
    "List programming languages, frameworks, and tools in requirements.tools_and_technologies (in addition to hard skill lists). "
    "Extract spoken language requirements into requirements.languages_required and optional languages into requirements.languages_optional. "
    "Put mentioned certifications (e.g. 'AWS ML Specialty') into requirements.certificates (mirror to requirements.certifications). "
    "Extract start dates (e.g. '01.10.2024', '2024-10-01', 'ab Herbst 2025') into meta.target_start_date in ISO format."
)


def USER_JSON_EXTRACT_TEMPLATE(
    fields_list: list[str], job_text: str, extras: dict | None = None
) -> str:
    """Render a user prompt for JSON field extraction.

    Args:
        fields_list: Fields to extract.
        job_text: Source text containing the information.
        extras: Optional additional context (e.g., title, url).

    Returns:
        A formatted prompt for the LLM user message.
    """

    extras = extras or {}
    extras_lines = [f"{k.capitalize()}: {v}" for k, v in extras.items() if v]
    extras_block = "\n".join(extras_lines)

    field_lines = "\n".join(f"- {f}" for f in fields_list)

    instructions = (
        "Extract the following fields and respond with a JSON object containing these keys. "
        "If data for a key is missing, use an empty string or empty list. Use position.job_title for the main job title without gender markers and map the employer name to company.name and the primary city to location.primary_city. List each responsibility/task separately in responsibilities.items.\n"
        f"Fields:\n{field_lines}"
    )

    if extras_block:
        prompt = f"{extras_block}\n\n{instructions}\n\nText:\n{job_text}"
    else:
        prompt = f"{instructions}\n\nText:\n{job_text}"
    return prompt


# ----------------------------------------------------------------------------
# Job-ad templates
# ----------------------------------------------------------------------------


def _stringify_brand_keywords(raw: Any) -> str:
    if isinstance(raw, (list, tuple, set)):
        return ", ".join(str(item).strip() for item in raw if str(item).strip())
    if raw is None:
        return ""
    return str(raw).strip()


def _format_section_block(section: Mapping[str, Any]) -> str:
    title = str(section.get("title") or section.get("group") or "").strip()
    entries: Sequence[Mapping[str, Any]] = section.get("entries", []) or []
    lines: list[str] = [title] if title else []
    for entry in entries:
        label = str(entry.get("label") or "").strip()
        items = entry.get("items") or []
        text = str(entry.get("text") or "").strip()
        if items:
            bullet_heading = f"- {label}:" if label else "-"
            lines.append(bullet_heading)
            for item in items:
                item_text = str(item).strip()
                if item_text:
                    lines.append(f"  * {item_text}")
        elif label or text:
            combined = text if not label else f"{label}: {text}" if text else label
            lines.append(f"- {combined}")
    return "\n".join(line for line in lines if line)


def build_job_ad_prompt(payload: Mapping[str, Any]) -> list[dict[str, str]]:
    """Return chat messages instructing the model to craft a job advertisement."""

    lang = str(payload.get("language") or "de").lower()

    system_msg = tr(
        "Du bist eine erfahrene Texterin für Stellenanzeigen. Schreibe klar, inklusiv und überzeugend.",
        "You are an experienced recruitment copywriter. Write clearly, inclusively, and persuasively.",
        lang,
    )

    heading = str(payload.get("heading") or payload.get("job_title") or "").strip()
    location = str(payload.get("location") or "").strip()
    summary = str(payload.get("summary") or "").strip()
    audience = str(payload.get("audience") or "").strip()
    tone = str(payload.get("tone") or "").strip()
    style_reference = str(payload.get("style_reference") or "").strip()
    brand_keywords = _stringify_brand_keywords(payload.get("brand_keywords"))
    cta_hint = str(payload.get("cta_hint") or "").strip()
    company_info = payload.get("company") or {}
    company_names = [
        str(company_info.get(key) or "").strip()
        for key in ("display_name", "brand_name", "legal_name")
    ]
    company_names = [name for name in company_names if name]
    if company_names:
        deduped = list(dict.fromkeys(company_names))
        company_line = ", ".join(deduped)
    else:
        company_line = ""

    sections: Sequence[Mapping[str, Any]] = payload.get("sections", []) or []
    manual_sections: Sequence[Mapping[str, Any]] = (
        payload.get("manual_sections") or []
    )
    sections_label = tr("Strukturierte Abschnitte", "Structured sections", lang)

    instruction_lines = [
        tr(
            "Schreibe eine wirkungsvolle Stellenanzeige in Markdown basierend auf den folgenden Daten.",
            "Write a compelling job advertisement in Markdown based on the structured data below.",
            lang,
        ),
        tr(
            "Beginne mit einer aufmerksamkeitsstarken H1-Überschrift und verwende klare Zwischenüberschriften.",
            "Start with an attention-grabbing H1 headline and use clear sub-headings.",
            lang,
        ),
        tr(
            "Verknüpfe Zielgruppe, Ton und Brand-Keywords auf natürliche Weise.",
            "Weave the audience, tone, and brand keywords naturally into the copy.",
            lang,
        ),
        tr(
            "Erwähne Jobtitel und wichtige Skills für SEO immer wieder organisch im Text.",
            "Repeat the job title and key skills naturally throughout the copy for SEO.",
            lang,
        ),
        tr(
            "Nutze Aufzählungen nur dort, wo sie den Text auflockern.",
            "Use bullet lists only when they improve readability.",
            lang,
        ),
        tr(
            "Schließe mit einem motivierenden Call-to-Action, der Bewerber:innen direkt anspricht.",
            "Close with a motivating call to action that directly invites candidates to apply.",
            lang,
        ),
        tr(
            f"Arbeite jede einzelne Information aus dem Block „{sections_label}“ sowie alle manuellen Zusatzabschnitte vollständig in den Anzeigentext ein – nichts weglassen oder zusammenfassen.",
            f"Incorporate every item from the \"{sections_label}\" block and any manual sections directly into the advertisement copy—do not omit or merge details.",
            lang,
        ),
    ]

    meta_lines: list[str] = []
    if heading:
        meta_lines.append(
            f"{tr('Überschrift', 'Heading', lang)}: {heading}"
        )
    if location:
        meta_lines.append(
            f"{tr('Standort', 'Location', lang)}: {location}"
        )
    if summary:
        meta_lines.append(
            f"{tr('Kurzprofil', 'Role summary', lang)}: {summary}"
        )
    if company_line:
        meta_lines.append(
            f"{tr('Unternehmen', 'Company', lang)}: {company_line}"
        )
    if audience:
        meta_lines.append(
            f"{tr('Zielgruppe', 'Target audience', lang)}: {audience}"
        )
    if tone:
        meta_lines.append(
            f"{tr('Ton', 'Tone', lang)}: {tone}"
        )
    if brand_keywords:
        label = tr("Brand-Keywords", "Brand keywords", lang)
        meta_lines.append(f"{label}: {brand_keywords}")
    if style_reference:
        meta_lines.append(
            f"{tr('Stilreferenz', 'Style reference', lang)}: {style_reference}"
        )
    if cta_hint:
        meta_lines.append(
            f"{tr('CTA-Hinweis', 'CTA hint', lang)}: {cta_hint}"
        )

    section_blocks = [
        block
        for block in (_format_section_block(section) for section in sections)
        if block
    ]

    manual_lines: list[str] = []
    for section in manual_sections:
        content = str(section.get("content") or "").strip()
        if not content:
            continue
        title = str(section.get("title") or "").strip()
        if title:
            manual_lines.append(f"{title}: {content}")
        else:
            manual_lines.append(content)

    parts = ["\n".join(instruction_lines)]
    if meta_lines:
        parts.append(f"{tr('Kontext', 'Context', lang)}:\n" + "\n".join(meta_lines))
    if section_blocks:
        parts.append(f"{sections_label}:\n" + "\n\n".join(section_blocks))
    if manual_lines:
        label = tr(
            "Kuratiere diese Zusatzabschnitte unverändert", "Include these curated sections verbatim", lang
        )
        parts.append(f"{label}:\n" + "\n".join(manual_lines))

    user_msg = "\n\n".join(part for part in parts if part).strip()

    messages = [{"role": "system", "content": system_msg}]
    if user_msg:
        messages.append({"role": "user", "content": user_msg})
    else:
        messages.append({"role": "user", "content": system_msg})
    return messages
