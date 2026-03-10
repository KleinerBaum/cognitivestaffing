from __future__ import annotations

from wizard.navigation_types import WizardContext

from ._shared import render_v2_step


def step_review(context: WizardContext) -> None:
    render_v2_step(
        context,
        title=("Review", "Review"),
        intro=(
            "Treffe finale Entscheidungen und exportiere die Ergebnisse.",
            "Confirm final decisions and export results.",
        ),
        missing_paths=(),
        known_fields=(("Open decisions", "open_decisions"), ("Warnings", "warnings")),
    )
