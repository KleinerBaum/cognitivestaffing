from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WizardSessionKeys:
    """Namespaced session-state keys for wizard navigation storage."""

    wizard_id: str

    @property
    def prefix(self) -> str:
        return f"wiz:{self.wizard_id}:"

    def namespace(self, key: str) -> str:
        return f"{self.prefix}{key}"

    @property
    def navigation_state(self) -> str:
        return self.namespace("navigation_state")
