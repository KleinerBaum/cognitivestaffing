"""Tests for company step dependency bindings."""

from importlib import reload

from wizard import flow
from wizard.steps import company_step


def test_bind_flow_dependencies_exposes_autofill_was_rejected() -> None:
    """Ensure company step binds autofill rejection helper from flow without errors."""

    reloaded_step = reload(company_step)

    reloaded_step._bind_flow_dependencies(flow)

    assert reloaded_step._autofill_was_rejected is flow._autofill_was_rejected


def test_bind_flow_dependencies_exposes_autofill_suggestion_renderer() -> None:
    """Ensure company step binds autofill suggestion helper from flow."""

    reloaded_step = reload(company_step)

    reloaded_step._bind_flow_dependencies(flow)

    assert reloaded_step._render_autofill_suggestion is flow._render_autofill_suggestion
