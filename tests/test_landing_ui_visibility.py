from __future__ import annotations

from pathlib import Path


def test_global_stepper_and_progress_are_guarded_on_landing() -> None:
    """App shell should hide global stepper/progress widgets on the landing step."""

    source = Path("app.py").read_text(encoding="utf-8")

    guard = 'if display_wiz.current_step().id != "landing":'
    assert guard in source

    guard_index = source.index(guard)
    stepper_call = source.index("render_stepper(display_wiz)")
    progress_call = source.index("render_progress_and_microcopy(display_wiz)")

    assert guard_index < stepper_call
    assert guard_index < progress_call
