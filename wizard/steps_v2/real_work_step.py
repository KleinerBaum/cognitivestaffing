from __future__ import annotations

from wizard.navigation_types import WizardContext

from ._shared import render_v2_step


def step_real_work(context: WizardContext) -> None:
    render_v2_step(
        context,
        title=("Real Work", "Real Work"),
        intro=(
            "Konkretisiere, was die Person im Alltag liefert.",
            "Clarify what the role delivers in day-to-day work.",
        ),
        missing_paths=("work.responsibilities",),
        known_fields=(("Responsibilities", "work.responsibilities"), ("Location", "work.location")),
    )
