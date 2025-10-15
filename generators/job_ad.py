"""Structured job ad generation."""

from __future__ import annotations

from typing import Any

from config import ModelTask, get_active_verbosity, get_model_for
from openai_utils import call_chat_api
from schemas import JOB_AD_SCHEMA

__all__ = ["generate_job_ad"]


def generate_job_ad(vacancy_json: dict, lang: str, tone: str = "professional") -> Any:
    """Generate a structured job ad JSON payload."""

    system = {
        "role": "system",
        "content": (
            "Du bist eine erfahrene Stellenanzeigen-Autorin nach GPT-5-Prompting-Standards. Plane intern eine kurze Gliederung"
            " (nicht ausgeben) und folge ihr Schritt für Schritt. Befolge diese Schritte: 1) Kontext und Ton verstehen, 2) Str"
            "uktur und Reihenfolge der Abschnitte festlegen, 3) jeden Abschnitt präzise ausformulieren, 4) prüfen, dass alle Fel"
            "der des JSON-Schemas gefüllt sind. Höre erst auf, wenn alle Anforderungen erfüllt sind, und liefere ausschließlich"
            " JSON nach Schema."
        ),
    }
    user = {
        "role": "user",
        "content": f"Sprache: {lang}\nTon: {tone}\nProfil:\n{vacancy_json}",
    }
    return call_chat_api(
        messages=[system, user],
        model=get_model_for(ModelTask.JOB_AD),
        temperature=0.4,
        json_schema={"name": "JobAd", "schema": JOB_AD_SCHEMA},
        task=ModelTask.JOB_AD,
        verbosity=get_active_verbosity(),
    )
