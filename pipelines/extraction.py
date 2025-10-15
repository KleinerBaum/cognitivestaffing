"""Structured vacancy extraction pipeline."""

from __future__ import annotations

from typing import Any

from config import ModelTask, get_active_verbosity, get_model_for
from openai_utils import call_chat_api
from schemas import VACANCY_EXTRACTION_SCHEMA

__all__ = ["extract_vacancy_structured"]


def extract_vacancy_structured(doc_text: str, lang: str) -> Any:
    """Extract a structured vacancy profile using JSON schema enforcement."""

    system = {
        "role": "system",
        "content": (
            "Du bist ein präziser HR-Extractor nach den GPT-5-Prompting-Guidelines. "
            "Plane gedanklich kurz deine Vorgehensweise (nicht ausgeben) und arbeite sie Schritt für Schritt ab. "
            "Folge diesen Schritten: 1) Kontext lesen, 2) Fakten den Schemafeldern zuordnen, 3) Ergebnis gegen das Schema validieren. "
            "Stoppe nicht, bevor die Anfrage vollständig erfüllt ist. "
            "Antworte ausschließlich mit validem JSON gemäß Schema – keine Erklärungen, kein Markdown."
        ),
    }
    user = {
        "role": "user",
        "content": f"Sprache: {lang}\nExtrahiere die Stellenausschreibung strukturiert:\n---\n{doc_text}\n---",
    }
    return call_chat_api(
        messages=[system, user],
        model=get_model_for(ModelTask.EXTRACTION),
        temperature=0.1,
        json_schema={"name": "VacancyExtraction", "schema": VACANCY_EXTRACTION_SCHEMA},
        task=ModelTask.EXTRACTION,
        verbosity=get_active_verbosity(),
    )
