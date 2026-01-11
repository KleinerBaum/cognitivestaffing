from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from wizard.debug.flow_diagram import build_mermaid_flowchart
from wizard.navigation_types import StepNextResolver, WizardContext


def _branch_next(_context: WizardContext, session_state: Mapping[str, object]) -> str:
    return "step_b" if session_state.get("flag") else "step_c"


@dataclass(frozen=True)
class DummyStep:
    key: str
    label: tuple[str, str]
    next_step_id: StepNextResolver | None = None
    required_fields: tuple[str, ...] = ()
    allow_skip: bool = False


def test_build_mermaid_flowchart_includes_branches_and_guards() -> None:
    steps = (
        DummyStep(key="step_a", label=("A", "A"), next_step_id=_branch_next),
        DummyStep(key="step_b", label=("B", "B"), required_fields=("field",)),
        DummyStep(key="step_c", label=("C", "C")),
    )

    mermaid = build_mermaid_flowchart(steps)

    assert "step_step_a" in mermaid
    assert "step_step_b" in mermaid
    assert "step_step_c" in mermaid
    assert 'session_state.get("flag")' in mermaid
    assert "|else|" in mermaid
    assert "Pflichtfelder fehlen / Missing required fields" in mermaid
    assert "step_step_b -.-> step_step_a" in mermaid
