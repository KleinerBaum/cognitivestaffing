"""Tests for team step dependency bindings."""

from importlib import reload

from wizard import flow
from wizard.steps import team_step


def test_bind_flow_dependencies_exposes_employment_toggle_help() -> None:
    """Team step binding should surface employment toggle copy from the flow module."""

    reloaded_step = reload(team_step)

    reloaded_step._bind_flow_dependencies(flow)

    assert reloaded_step.EMPLOYMENT_OVERTIME_TOGGLE_HELP is flow.EMPLOYMENT_OVERTIME_TOGGLE_HELP
    assert reloaded_step.EMPLOYMENT_SECURITY_TOGGLE_HELP is flow.EMPLOYMENT_SECURITY_TOGGLE_HELP
    assert reloaded_step.EMPLOYMENT_SHIFT_TOGGLE_HELP is flow.EMPLOYMENT_SHIFT_TOGGLE_HELP
