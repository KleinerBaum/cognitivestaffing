from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping, Sequence

@dataclass(frozen=True)
class WizardContext:
    """Context passed to step renderer callables."""

    schema: Mapping[str, object]
    critical_fields: Sequence[str]


@dataclass(frozen=True)
class StepRenderer:
    """Callable wrapper with legacy index mapping for Streamlit state sync."""

    callback: Callable[[WizardContext], None]
    legacy_index: int
