"""Structured vacancy extraction pipeline."""

from __future__ import annotations

from typing import Any

from config import ModelTask
from openai_utils import call_chat_api
from schemas import VACANCY_EXTRACTION_SCHEMA

__all__ = ["extract_vacancy_structured"]


def extract_vacancy_structured(doc_text: str, lang: str) -> Any:
    """Extract a structured vacancy profile using JSON schema enforcement."""

    system = {
        "role": "system",
        "content": (
            "Du bist ein präziser HR-Extractor. "
            "Gib ausschließlich valide JSON gemäß Schema zurück. "
            "Keine Erklärungen, kein Markdown."
        ),
    }
    user = {
        "role": "user",
        "content": f"Sprache: {lang}\nExtrahiere die Stellenausschreibung strukturiert:\n---\n{doc_text}\n---",
    }
    return call_chat_api(
        messages=[system, user],
        model="gpt-5-mini",
        temperature=0.1,
        json_schema={"name": "VacancyExtraction", "schema": VACANCY_EXTRACTION_SCHEMA},
        task=ModelTask.EXTRACTION,
    )
