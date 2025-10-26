from __future__ import annotations

from .base import WizardPage


PAGE = WizardPage(
    key="skills",
    label=("Skills & Anforderungen", "Skills & Requirements"),
    panel_header=("Skill-Portfolio", "Skill portfolio"),
    panel_subheader=("Muss & Nice-to-have", "Must & nice-to-have"),
    panel_intro_variants=(
        (
            "Halte die wichtigsten Skills strukturiert fest.",
            "Capture the key skills in a structured way.",
        ),
        (
            "Diese Angaben steuern Matching, Benchmarks und Exporte.",
            "These values power matching, benchmarks, and exports.",
        ),
    ),
    required_fields=(
        "requirements.hard_skills_required",
        "requirements.soft_skills_required",
    ),
    summary_fields=(
        "requirements.hard_skills_required",
        "requirements.soft_skills_required",
        "requirements.tools_and_technologies",
        "requirements.languages_required",
    ),
    allow_skip=False,
)
