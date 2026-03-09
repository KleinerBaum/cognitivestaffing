"""Tests for targeted second-pass list extraction helpers."""

from __future__ import annotations

from wizard.services.targeted_list_extraction import (
    build_targeted_cue_context,
    merge_list_entries,
)


def test_build_targeted_cue_context_handles_indirect_german_and_english_ads() -> None:
    text = """
    What you'll do: Partner with product and keep stakeholders aligned.
    You will shape architecture decisions and mentor engineers.
    Ihr Profil: Erfahrung in Python und SQL sowie selbstständige Arbeitsweise.
    Anforderungen: Sicheres Auftreten und Teamfähigkeit.
    """

    context = build_targeted_cue_context(
        text,
        [
            "responsibilities.items",
            "requirements.hard_skills_required",
            "requirements.soft_skills_required",
        ],
    )

    assert "responsibilities.items" in context
    assert "requirements.hard_skills_required" in context
    assert "requirements.soft_skills_required" in context
    assert "Erfahrung in Python" in context
    assert "stakeholders aligned" in context


def test_merge_list_entries_keeps_existing_and_adds_missing_deduplicated() -> None:
    existing = ["Python", "Stakeholder management"]
    incoming = ["python", "SQL", "Stakeholder management", "Communication"]

    merged = merge_list_entries(existing, incoming)

    assert merged == ["Python", "Stakeholder management", "SQL", "Communication"]
