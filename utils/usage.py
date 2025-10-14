"""Helpers for aggregating and presenting token usage."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Iterable

from config import ModelTask
from utils.i18n import tr

__all__ = ["usage_totals", "build_usage_rows", "build_usage_markdown"]


_TASK_LABELS: dict[str, tuple[str, str]] = {
    ModelTask.DEFAULT.value: ("Allgemein", "General"),
    ModelTask.EXTRACTION.value: ("Extraktion", "Extraction"),
    ModelTask.COMPANY_INFO.value: ("Unternehmensinfos", "Company info"),
    ModelTask.FOLLOW_UP_QUESTIONS.value: ("Follow-up-Fragen", "Follow-up questions"),
    ModelTask.RAG_SUGGESTIONS.value: ("Kontextvorschläge", "Context suggestions"),
    ModelTask.SKILL_SUGGESTION.value: ("Skill-Vorschläge", "Skill suggestions"),
    ModelTask.BENEFIT_SUGGESTION.value: ("Benefit-Vorschläge", "Benefit suggestions"),
    ModelTask.TASK_SUGGESTION.value: ("Aufgaben", "Task suggestions"),
    ModelTask.ONBOARDING_SUGGESTION.value: ("Onboarding", "Onboarding"),
    ModelTask.JOB_AD.value: ("Stellenanzeige", "Job ad"),
    ModelTask.INTERVIEW_GUIDE.value: ("Interview-Guide", "Interview guide"),
    ModelTask.PROFILE_SUMMARY.value: ("Profil-Zusammenfassung", "Profile summary"),
    ModelTask.CANDIDATE_MATCHING.value: ("Kandidat:innen-Matching", "Candidate matching"),
    ModelTask.DOCUMENT_REFINEMENT.value: ("Dokument-Feinschliff", "Document refinement"),
    ModelTask.EXPLANATION.value: ("Erklärungen", "Explanations"),
    "salary_estimate": ("Gehaltsprognose", "Salary estimate"),
}


def _to_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _task_label(task_key: str) -> str:
    de_en = _TASK_LABELS.get(task_key)
    if de_en:
        return tr(*de_en)
    cleaned = task_key.replace("_", " ").strip()
    return cleaned.title() if cleaned else tr("Unbekannt", "Unknown")


def usage_totals(usage: Mapping[str, Any]) -> tuple[int, int, int]:
    """Return overall input/output totals from ``usage``."""

    input_tokens = _to_int(usage.get("input_tokens"))
    output_tokens = _to_int(usage.get("output_tokens"))
    return input_tokens, output_tokens, input_tokens + output_tokens


def _iter_task_stats(tasks: Mapping[str, Any]) -> Iterable[tuple[str, int, int]]:
    for key, raw_stats in tasks.items():
        if not isinstance(raw_stats, Mapping):
            continue
        input_tokens = _to_int(raw_stats.get("input"))
        if not input_tokens and "input" not in raw_stats:
            input_tokens = _to_int(raw_stats.get("input_tokens"))
        output_tokens = _to_int(raw_stats.get("output"))
        if not output_tokens and "output" not in raw_stats:
            output_tokens = _to_int(raw_stats.get("output_tokens"))
        if input_tokens or output_tokens:
            yield key, input_tokens, output_tokens


def build_usage_rows(usage: Mapping[str, Any]) -> list[tuple[str, int, int, int]]:
    """Return per-task usage rows ``(label, input, output, total)``."""

    tasks_section = {}
    if isinstance(usage.get("by_task"), Mapping):
        tasks_section = usage.get("by_task", {})
    elif isinstance(usage.get("tasks"), Mapping):
        tasks_section = usage.get("tasks", {})

    rows: list[tuple[str, int, int, int]] = []
    for task_key, input_tokens, output_tokens in _iter_task_stats(tasks_section):
        label = _task_label(task_key)
        total = input_tokens + output_tokens
        rows.append((label, input_tokens, output_tokens, total))

    rows.sort(key=lambda item: (-item[3], item[0].lower()))
    return rows


def build_usage_markdown(usage: Mapping[str, Any]) -> str | None:
    """Return a Markdown table representing per-task usage or ``None``."""

    rows = build_usage_rows(usage)
    if not rows:
        return None

    header = "| {task} | {inp} | {out} | {total} |".format(
        task=tr("Aufgabe", "Task"),
        inp=tr("Input", "Input"),
        out=tr("Output", "Output"),
        total=tr("Summe", "Total"),
    )
    separator = "| --- | ---: | ---: | ---: |"
    lines = [header, separator]
    for label, input_tokens, output_tokens, total in rows:
        lines.append(f"| {label} | {input_tokens} | {output_tokens} | {total} |")
    return "\n".join(lines)
