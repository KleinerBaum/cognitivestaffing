from __future__ import annotations

from .base import WizardPage


_REQUIRED_FIELDS: tuple[str, ...] = ("skills.must_have",)
_SUMMARY_FIELDS: tuple[str, ...] = (
    "skills.must_have",
    "skills.nice_to_have",
    "skills.certifications",
    "skills.tools",
    "skills.languages",
)


PAGE = WizardPage(
    key="skills",
    label=("Kompetenzen", "Skills"),
    panel_header=("Skill-Portfolio", "Skill portfolio"),
    panel_subheader=("Muss & Nice-to-have", "Must & nice-to-have"),
    panel_intro_variants=(
        (
            "Lege fest, welche Kompetenzen zwingend und welche optional sind.",
            "Specify which competencies are mandatory and which are optional.",
        ),
        (
            "Sauber strukturierte Skill-Daten verbessern Scoring, Marktvergleiche und Exportqualität.",
            "Well-structured skill data improves scoring, market benchmarks, and export quality.",
        ),
        (
            "Markiere locker, was die Person wirklich können muss – den Rest packen wir unter Nice-to-have.",
            "Flag what this person absolutely needs to know and we’ll park the rest as nice-to-have.",
        ),
    ),
    required_fields=_REQUIRED_FIELDS,
    summary_fields=_SUMMARY_FIELDS,
    allow_skip=False,
)
