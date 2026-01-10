from __future__ import annotations

from typing import Mapping

from wizard.navigation.router import NavigationController
from wizard.navigation_types import StepRenderer, WizardContext
from wizard_pages.base import WizardPage


class _QueryParams(dict):
    def get_all(self, key: str) -> list[str]:
        value = self.get(key)
        if value is None:
            return []
        if isinstance(value, list):
            return [item for item in value if isinstance(item, str)]
        if isinstance(value, str):
            return [value]
        return []


def _build_page(key: str) -> WizardPage:
    return WizardPage(
        key=key,
        label=("Label", "Label"),
        panel_header=("Header", "Header"),
        panel_subheader=("Sub", "Sub"),
        panel_intro_variants=(("Intro", "Intro"),),
    )


def _build_renderers(keys: list[str]) -> dict[str, StepRenderer]:
    def _callback(_: WizardContext) -> None:
        return None

    return {key: StepRenderer(callback=_callback, legacy_index=index) for index, key in enumerate(keys)}


def _noop_value_resolver(_: Mapping[str, object], __: str, ___: object | None) -> object | None:
    return None


def test_sync_with_query_params_sets_current_step() -> None:
    pages = [_build_page("alpha"), _build_page("beta")]
    renderers = _build_renderers([page.key for page in pages])
    query_params = _QueryParams(step="beta")
    session_state: dict[str, object] = {}
    controller = NavigationController(
        pages=pages,
        renderers=renderers,
        context=WizardContext(schema={}, critical_fields=()),
        value_resolver=_noop_value_resolver,
        required_field_validators={},
        validated_fields=set(),
        query_params=query_params,
        session_state=session_state,
    )

    controller.sync_with_query_params()

    assert controller.get_current_step_key() == "beta"
    assert controller.state["current_step"] == "beta"
    assert query_params["step"] == "beta"
