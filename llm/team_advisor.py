"""Team composition advisor powered by the OpenAI Responses API."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from config import REASONING_EFFORT
from config.models import ModelTask, get_model_for
from llm.openai_responses import build_json_schema_format, call_responses_safe
from llm.response_schemas import TEAM_ADVICE_SCHEMA_NAME, get_response_schema
from prompts import prompt_registry

logger = logging.getLogger(__name__)


@dataclass
class TeamAdvice:
    """Structured response from the team advisor."""

    message: str
    reporting_line: str | None = None
    direct_reports: int | None = None
    follow_up_question: str | None = None


def _normalize_lang(lang: str | None) -> str:
    return "de" if str(lang or "de").lower().startswith("de") else "en"


def _fallback_message(lang: str) -> str:
    if lang == "de":
        return "Ich konnte gerade keinen Vorschlag generieren. Versuch es bitte erneut."
    return "I couldn't generate a suggestion right now. Please try again."


def _build_context_block(profile: Mapping[str, Any]) -> str:
    position = profile.get("position", {}) if isinstance(profile, Mapping) else {}
    company = profile.get("company", {}) if isinstance(profile, Mapping) else {}
    team = profile.get("team", {}) if isinstance(profile, Mapping) else {}

    context_parts: list[str] = []
    job_title = str(position.get("job_title") or "").strip()
    if job_title:
        context_parts.append(f"Role title: {job_title}")

    seniority = str(position.get("seniority_level") or "").strip()
    if seniority:
        context_parts.append(f"Seniority: {seniority}")

    company_size = str(company.get("size") or "").strip()
    if company_size:
        context_parts.append(f"Company size: {company_size}")

    reporting_line = str(team.get("reporting_line") or position.get("reports_to") or "").strip()
    if reporting_line:
        context_parts.append(f"Current reporting line: {reporting_line}")

    direct_reports = position.get("supervises")
    try:
        direct_reports_int = int(direct_reports) if direct_reports is not None else None
    except (TypeError, ValueError):
        direct_reports_int = None
    if direct_reports_int is not None:
        context_parts.append(f"Direct reports: {direct_reports_int}")

    team_name = str(team.get("name") or "").strip()
    if team_name:
        context_parts.append(f"Team name: {team_name}")

    mission = str(team.get("mission") or "").strip()
    if mission:
        context_parts.append(f"Team mission: {mission}")

    return "\n".join(context_parts)


def _build_messages(
    history: Sequence[Mapping[str, str]] | None,
    profile: Mapping[str, Any],
    lang: str,
    user_input: str | None,
) -> list[dict[str, Any]]:
    system_prompt = prompt_registry.format(
        "assistant.team_advisor.system",
        locale=lang,
        default=(
            "You are a concise HR assistant. Suggest realistic reporting lines and team sizes "
            "for the role using the provided context. Ask for confirmation before applying updates "
            "and keep answers short."
        ),
    )

    context_block = _build_context_block(profile)
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": [{"type": "text", "text": system_prompt}]},
        {"role": "user", "content": [{"type": "text", "text": context_block}]},
    ]

    for item in history or []:
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        role = str(item.get("role") or "user")
        messages.append({"role": role, "content": [{"type": "text", "text": content}]})

    if user_input:
        messages.append({"role": "user", "content": [{"type": "text", "text": user_input}]})
    else:
        starter = prompt_registry.format(
            "assistant.team_advisor.starter",
            locale=lang,
            default=(
                "Suggest a realistic reporting line and approximate number of direct reports for this role. "
                "If details are missing, ask one clarifying question."
            ),
        )
        messages.append({"role": "user", "content": [{"type": "text", "text": starter}]})

    return messages


def advise_team_structure(
    history: Sequence[Mapping[str, str]] | None,
    profile: Mapping[str, Any],
    *,
    lang: str = "de",
    user_input: str | None = None,
) -> TeamAdvice:
    """Return an assistant suggestion for team structure and reporting lines."""

    locale = _normalize_lang(lang)
    messages = _build_messages(history, profile, locale, user_input)
    response_format = build_json_schema_format(
        name=TEAM_ADVICE_SCHEMA_NAME,
        schema=get_response_schema(TEAM_ADVICE_SCHEMA_NAME),
        strict=True,
    )
    model = get_model_for(ModelTask.TEAM_ADVICE)
    result = call_responses_safe(
        messages,
        model=model,
        response_format=response_format,
        reasoning_effort=REASONING_EFFORT,
        task=str(ModelTask.TEAM_ADVICE),
    )
    if result is None:
        fallback = _fallback_message(locale)
        return TeamAdvice(message=fallback)

    content = (result.content or "").strip()
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        logger.warning("Team advisor returned non-JSON payload; using raw content")
        message = content or _fallback_message(locale)
        return TeamAdvice(message=message)

    message = str(payload.get("assistant_message") or content or _fallback_message(locale)).strip()
    reporting_line = str(payload.get("reporting_line_suggestion") or "").strip() or None

    direct_reports_raw = payload.get("direct_reports_suggestion")
    direct_reports: int | None
    if isinstance(direct_reports_raw, int):
        direct_reports = max(direct_reports_raw, 0)
    elif isinstance(direct_reports_raw, str):
        try:
            direct_reports = max(int(direct_reports_raw.strip()), 0)
        except (TypeError, ValueError):
            direct_reports = None
    else:
        direct_reports = None

    follow_up_question = str(payload.get("follow_up_question") or "").strip() or None

    return TeamAdvice(
        message=message,
        reporting_line=reporting_line,
        direct_reports=direct_reports,
        follow_up_question=follow_up_question,
    )


__all__ = ["TeamAdvice", "advise_team_structure"]
