from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Tuple


@dataclass(frozen=True)
class WizardPage:
    """Static metadata describing an individual wizard step.

    The router keeps this metadata separate from the rendering logic so that
    we can harmonise navigation, query-parameter routing, and localisation
    rules across different UI implementations.  Each ``WizardPage`` exposes
    translated labels alongside the fields that should be highlighted in the
    collected-values panel for the step.
    """

    key: str
    label: Tuple[str, str]
    panel_header: Tuple[str, str]
    panel_subheader: Tuple[str, str]
    panel_intro_variants: Tuple[Tuple[str, str], ...]
    required_fields: Tuple[str, ...] = ()
    summary_fields: Tuple[str, ...] = ()
    allow_skip: bool = False

    def translate(self, pair: Tuple[str, str], lang: str) -> str:
        """Return the language-specific variant from ``pair``."""

        if lang.lower().startswith("de"):
            return pair[0]
        return pair[1]

    def label_for(self, lang: str) -> str:
        """Return the localised label for the step."""

        return self.translate(self.label, lang)

    def header_for(self, lang: str) -> str:
        """Return the localised panel header."""

        return self.translate(self.panel_header, lang)

    def subheader_for(self, lang: str) -> str:
        """Return the localised panel subheader."""

        return self.translate(self.panel_subheader, lang)

    def intro_variants_for(self, lang: str) -> Iterable[str]:
        """Yield localised intro variants for the panel."""

        for pair in self.panel_intro_variants:
            yield self.translate(pair, lang)
