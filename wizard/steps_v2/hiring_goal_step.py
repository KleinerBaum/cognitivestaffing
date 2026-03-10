from __future__ import annotations

from wizard.navigation_types import WizardContext

from ._shared import render_v2_step


def step_hiring_goal(context: WizardContext) -> None:
    render_v2_step(
        context,
        title=("Hiring Goal", "Hiring Goal"),
        intro=(
            "Definiere Zielbild, Seniorität und Teamkontext der Rolle.",
            "Define role target state, seniority, and team context.",
        ),
        missing_paths=("role.title", "role.summary"),
        known_fields=(("Role title", "role.title"), ("Department", "role.department")),
    )
