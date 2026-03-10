from __future__ import annotations

from wizard.navigation_types import WizardContext

from ._shared import render_v2_step


def step_requirements_board(context: WizardContext) -> None:
    render_v2_step(
        context,
        title=("Requirements Board", "Requirements Board"),
        intro=(
            "Priorisiere Muss-/Kann-Kriterien für Suche und Entscheidung.",
            "Prioritize must-have and nice-to-have criteria for search and selection.",
        ),
        missing_paths=("requirements.hard_skills_required",),
        known_fields=(("Must-have skills", "requirements.hard_skills_required"),),
    )
