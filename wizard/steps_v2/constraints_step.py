from __future__ import annotations

from wizard.navigation_types import WizardContext

from ._shared import render_v2_step


def step_constraints(context: WizardContext) -> None:
    render_v2_step(
        context,
        title=("Constraints", "Constraints"),
        intro=(
            "Halte nicht verhandelbare Rahmenbedingungen fest.",
            "Capture hard constraints and non-negotiables.",
        ),
        missing_paths=("constraints.timeline",),
        known_fields=(("Salary min", "constraints.salary_min"), ("Timeline", "constraints.timeline")),
    )
