"""Definitions for user-selectable content style variants."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Tuple


@dataclass(frozen=True)
class StyleVariant:
    """Metadata describing a selectable content style."""

    label: Tuple[str, str]
    description: Tuple[str, str]
    instruction: Tuple[str, str]
    prompt_hint: Tuple[str, str]
    example: Tuple[str, str]


STYLE_VARIANT_ORDER: Final[tuple[str, ...]] = (
    "short_pragmatic",
    "professional",
    "casual",
)


STYLE_VARIANTS: Final[dict[str, StyleVariant]] = {
    "short_pragmatic": StyleVariant(
        label=("Kurz & pragmatisch", "Short & pragmatic"),
        description=(
            "Fokussiere dich auf das Wesentliche mit knappen, handlungsorientierten Formulierungen.",
            "Focus on the essentials with concise, action-driven phrasing.",
        ),
        instruction=(
            "kurz, pragmatisch und handlungsorientiert",
            "short, pragmatic, and action-oriented",
        ),
        prompt_hint=(
            "Nutze einen kompakten, pragmatischen Ton und fasse Vorschläge in wenigen Worten zusammen.",
            "Adopt a compact, pragmatic tone and keep each suggestion to just a few words.",
        ),
        example=(
            'Beispiel: "Kick-off mit klaren Zielen und messbaren Deliverables."',
            'Example: "Kick off with clear goals and measurable deliverables."',
        ),
    ),
    "professional": StyleVariant(
        label=("Fachlich & präzise", "Professional & precise"),
        description=(
            "Technisch fundierte, strukturierte Formulierungen mit fachlichem Tiefgang.",
            "Technically grounded, well-structured phrasing with professional depth.",
        ),
        instruction=(
            "fachlich präzise, strukturiert und professionell",
            "professional, technically precise, and well-structured",
        ),
        prompt_hint=(
            "Formuliere professionell, strukturiert und mit klarem fachlichem Fokus.",
            "Write in a professional, structured tone with a clear technical focus.",
        ),
        example=(
            'Beispiel: "Erstelle eine strukturierte Übergabe mit klar definierten Verantwortlichkeiten."',
            'Example: "Prepare a structured handover outlining clearly assigned responsibilities."',
        ),
    ),
    "casual": StyleVariant(
        label=("Locker & freundlich", "Casual & friendly"),
        description=(
            "Lockerer, motivierender Ton mit nahbarer Ansprache.",
            "Relaxed, encouraging tone with an approachable voice.",
        ),
        instruction=(
            "locker, freundlich und motivierend",
            "casual, friendly, and encouraging",
        ),
        prompt_hint=(
            "Kling locker, freundlich und motivierend – wie in einem persönlichen Gespräch.",
            "Sound casual, friendly, and motivating – like a personable conversation.",
        ),
        example=(
            'Beispiel: "Starte mit einem warmen Willkommen und lade zum Austausch auf Augenhöhe ein."',
            'Example: "Begin with a warm welcome and invite an open, friendly exchange."',
        ),
    ),
}


__all__ = ["StyleVariant", "STYLE_VARIANTS", "STYLE_VARIANT_ORDER"]
