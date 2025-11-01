"""Prompt templates for LLM interactions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from core.schema import ALL_FIELDS
from prompts import prompt_registry
from utils.i18n import tr

# ----------------------------------------------------------------------------
# Field enumeration
# ----------------------------------------------------------------------------

# Export schema order for prompt rendering
FIELDS_ORDER: list[str] = ALL_FIELDS


@dataclass(slots=True)
class PreExtractionInsights:
    """Hints derived from a preliminary document analysis."""

    summary: str = ""
    relevant_fields: list[str] | None = None
    missing_fields: list[str] | None = None

    def has_data(self) -> bool:
        """Return ``True`` when any hint is populated."""

        return bool(
            (self.summary and self.summary.strip())
            or (self.relevant_fields and any(self.relevant_fields))
            or (self.missing_fields and any(self.missing_fields))
        )


def render_field_bullets() -> str:
    """Return fields as a bullet list in schema order."""
    return "\n".join(f"- {field}" for field in FIELDS_ORDER)


# ----------------------------------------------------------------------------
# Extraction templates
# ----------------------------------------------------------------------------

SYSTEM_JSON_EXTRACTOR: str = prompt_registry.get("llm.json_extractor.system")
USER_JSON_EXTRACT_BASE: str = prompt_registry.get("llm.json_extractor.user_base")
USER_JSON_EXTRACT_LOCKED_HINT: str = prompt_registry.get("llm.json_extractor.locked_user_hint")
LOCKED_BLOCK_HEADING: str = prompt_registry.get("llm.json_extractor.locked_block_heading")
FOCUS_REMAINING_HINT: str = prompt_registry.get("llm.json_extractor.focus_remaining_hint")
FOCUS_FIELDS_HINT: str = prompt_registry.get("llm.json_extractor.focus_fields_hint")
ALL_LOCKED_HINT: str = prompt_registry.get("llm.json_extractor.all_locked_hint")


def build_user_json_extract_prompt(
    fields_list: list[str],
    job_text: str,
    extras: dict | None = None,
    *,
    locked_fields: Mapping[str, str] | None = None,
    insights: PreExtractionInsights | None = None,
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

    locked = locked_fields or {}
    locked_fields_list: list[str] = []
    for field, value in locked.items():
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        locked_fields_list.append(field)
    locked_block = ""
    if locked_fields_list:
        locked_block = "\n".join([LOCKED_BLOCK_HEADING] + [f"  - {field}" for field in locked_fields_list])

    field_lines = "\n".join(f"- {f}" for f in fields_list)

    instructions = USER_JSON_EXTRACT_BASE
    if locked_block:
        instructions = f"{instructions} {USER_JSON_EXTRACT_LOCKED_HINT}"

    reduced_fields = len(fields_list) < len(FIELDS_ORDER)

    if fields_list:
        if locked_block and reduced_fields:
            instructions += "\n" + FOCUS_REMAINING_HINT + field_lines
        else:
            instructions += "\n" + FOCUS_FIELDS_HINT + field_lines
    else:
        instructions += "\n" + ALL_LOCKED_HINT

    analysis_block = ""
    if insights and insights.has_data():
        analysis_lines: list[str] = ["Pre-analysis highlights:"]
        if insights.summary and insights.summary.strip():
            analysis_lines.append(insights.summary.strip())
        if insights.relevant_fields:
            filtered = [field.strip() for field in insights.relevant_fields if field and field.strip()]
            if filtered:
                analysis_lines.append("Likely evidence for these fields:")
                analysis_lines.extend(f"  - {field}" for field in filtered)
        if insights.missing_fields:
            missing_filtered = [field.strip() for field in insights.missing_fields if field and field.strip()]
            if missing_filtered:
                analysis_lines.append("Potential gaps or missing details:")
                analysis_lines.extend(f"  - {field}" for field in missing_filtered)
        analysis_block = "\n".join(analysis_lines)

    blocks: list[str] = []
    if extras_block:
        blocks.append(extras_block)
    if locked_block:
        blocks.append(locked_block)
    if analysis_block:
        blocks.append(analysis_block)
    blocks.append(instructions)
    blocks.append(f"Text:\n{job_text}")
    prompt = "\n\n".join(blocks)
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

    system_msg = prompt_registry.get("generators.job_ad.system", locale=lang)

    heading = str(payload.get("heading") or payload.get("job_title") or "").strip()
    location = str(payload.get("location") or "").strip()
    summary = str(payload.get("summary") or "").strip()
    audience = str(payload.get("audience") or "").strip()
    tone = str(payload.get("tone") or "").strip()
    style_reference = str(payload.get("style_reference") or "").strip()
    brand_keywords = _stringify_brand_keywords(payload.get("brand_keywords"))
    cta_hint = str(payload.get("cta_hint") or "").strip()
    company_info = payload.get("company") or {}
    company_names = [str(company_info.get(key) or "").strip() for key in ("display_name", "brand_name", "legal_name")]
    company_names = [name for name in company_names if name]
    if company_names:
        deduped = list(dict.fromkeys(company_names))
        company_line = ", ".join(deduped)
    else:
        company_line = ""

    sections: Sequence[Mapping[str, Any]] = payload.get("sections", []) or []
    manual_sections: Sequence[Mapping[str, Any]] = payload.get("manual_sections") or []
    sections_label = tr("Strukturierte Abschnitte", "Structured sections", lang)

    instruction_templates = prompt_registry.get("generators.job_ad.instructions", locale=lang)
    instruction_lines = [str(template).format(sections_label=sections_label) for template in instruction_templates]

    meta_lines: list[str] = []
    if heading:
        meta_lines.append(f"{tr('Überschrift', 'Heading', lang)}: {heading}")
    if location:
        meta_lines.append(f"{tr('Standort', 'Location', lang)}: {location}")
    if summary:
        meta_lines.append(f"{tr('Kurzprofil', 'Role summary', lang)}: {summary}")
    if company_line:
        meta_lines.append(f"{tr('Unternehmen', 'Company', lang)}: {company_line}")
    if audience:
        meta_lines.append(f"{tr('Zielgruppe', 'Target audience', lang)}: {audience}")
    if tone:
        meta_lines.append(f"{tr('Ton', 'Tone', lang)}: {tone}")
    if brand_keywords:
        label = tr("Brand-Keywords", "Brand keywords", lang)
        meta_lines.append(f"{label}: {brand_keywords}")
    branding_info = payload.get("branding") or {}
    claim = str(branding_info.get("claim") or company_info.get("claim") or "").strip()
    brand_color = str(branding_info.get("brand_color") or company_info.get("brand_color") or "").strip()
    logo_url = str(branding_info.get("logo_url") or company_info.get("logo_url") or "").strip()
    if claim:
        meta_lines.append(f"{tr('Claim/Slogan', 'Claim/tagline', lang)}: {claim}")
    if brand_color:
        meta_lines.append(f"{tr('Markenfarbe', 'Brand colour', lang)}: {brand_color}")
    if logo_url:
        meta_lines.append(f"{tr('Logo-Quelle', 'Logo source', lang)}: {logo_url}")
    if style_reference:
        meta_lines.append(f"{tr('Stilreferenz', 'Style reference', lang)}: {style_reference}")
    if cta_hint:
        meta_lines.append(f"{tr('CTA-Hinweis', 'CTA hint', lang)}: {cta_hint}")

    section_blocks = [block for block in (_format_section_block(section) for section in sections) if block]

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
        label = tr("Kuratiere diese Zusatzabschnitte unverändert", "Include these curated sections verbatim", lang)
        parts.append(f"{label}:\n" + "\n".join(manual_lines))

    user_msg = "\n\n".join(part for part in parts if part).strip()

    messages = [{"role": "system", "content": system_msg}]
    if user_msg:
        messages.append({"role": "user", "content": user_msg})
    else:
        messages.append({"role": "user", "content": system_msg})
    return messages
