"""Structured vacancy extraction pipeline."""

from __future__ import annotations

from typing import Any

from config import get_active_verbosity
from config.models import ModelTask, get_model_for
from openai_utils import call_chat_api
from prompts import prompt_registry
from core.schema_registry import get_canonical_json_schema

__all__ = ["extract_vacancy_structured"]


def extract_vacancy_structured(doc_text: str, lang: str) -> Any:
    """Extract a structured vacancy profile using JSON schema enforcement."""

    system = {
        "role": "system",
        "content": prompt_registry.get("pipelines.extraction.system"),
    }
    user = {
        "role": "user",
        "content": f"Sprache: {lang}\nExtrahiere die Stellenausschreibung strukturiert:\n---\n{doc_text}\n---",
    }
    return call_chat_api(
        messages=[system, user],
        model=get_model_for(ModelTask.EXTRACTION),
        temperature=0.1,
        json_schema={
            "name": "VacancyExtraction",
            "schema": get_canonical_json_schema(schema_version="v1", artifact="vacancy_extraction"),
        },
        task=ModelTask.EXTRACTION,
        verbosity=get_active_verbosity(),
    )
