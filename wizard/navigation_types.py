from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence


@dataclass(frozen=True)
class WizardContext:
    """Context passed to step renderer callables."""

    schema: Mapping[str, object]
    critical_fields: Sequence[str]
    profile_updater: Callable[[str, Any], None] | None = None
    next_step_callback: Callable[[], None] | None = None

    def update_profile(self, path: str, value: Any) -> None:
        """Persist a profile value at the provided dotted path."""

        if self.profile_updater is None:
            return
        self.profile_updater(path, value)

    def next_step(self) -> None:
        """Advance to the next wizard step."""

        if self.next_step_callback is None:
            return
        self.next_step_callback()


StepNextResolver = Callable[[WizardContext, Mapping[str, object]], str | None]


@dataclass(frozen=True)
class StepRenderer:
    """Callable wrapper with legacy index mapping for Streamlit state sync."""

    callback: Callable[[WizardContext], None]
    legacy_index: int
