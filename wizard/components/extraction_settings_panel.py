from __future__ import annotations

from typing import Any, Callable

import streamlit as st

import config.models as model_config
from constants.keys import StateKeys, UIKeys
from utils.i18n import tr


def render_extraction_settings_panel(
    apply_parsing_mode: Callable[[str], str],
    queue_extraction_rerun: Callable[[], None],
    *,
    st_module: Any = st,
) -> None:
    """Render parsing controls for structured extraction."""

    mode_options: tuple[str, ...] = ("quick", "precise")
    current_mode = str(st_module.session_state.get(StateKeys.REASONING_MODE, "precise") or "precise").lower()
    try:
        mode_index = mode_options.index(current_mode if current_mode in mode_options else "precise")
    except ValueError:
        mode_index = 1
    mode_labels = {
        "quick": tr("⚡ Schnell (Parsing)", "⚡ Fast (parsing)"),
        "precise": tr("🎯 Gründlich (Parsing)", "🎯 Thorough (parsing)"),
    }

    with st_module.expander(tr("Extraktionseinstellungen", "Extraction settings"), expanded=False, icon="🛠️"):
        st_module.caption(
            tr(
                "Passe das Parsing live an – wähle zwischen Schnell vs. Gründlich. Striktes JSON bleibt immer aktiv.",
                "Adjust parsing on the fly – choose Fast vs. Thorough. Strict JSON enforcement stays on by default.",
            )
        )

        selected_mode = st_module.radio(
            tr("Parsing-Modus: ⚡ Schnell vs. 🎯 Gründlich", "Parsing mode: ⚡ Fast vs. 🎯 Thorough"),
            options=mode_options,
            index=mode_index,
            key=UIKeys.EXTRACTION_REASONING_MODE,
            format_func=lambda value: mode_labels.get(value, value.title()),
            horizontal=True,
        )
        apply_parsing_mode(selected_mode)
        st_module.caption(
            tr(
                (
                    f"Schnell nutzt {model_config.LIGHTWEIGHT_MODEL} mit minimalem Denkaufwand; "
                    f"Gründlich erhöht den REASONING_EFFORT und wählt ein präziseres Modell "
                    f"({model_config.REASONING_MODEL} mit {model_config.O4_MINI}/{model_config.O3} Fallback)."
                ),
                (
                    f"Fast leans on {model_config.LIGHTWEIGHT_MODEL} with minimal reasoning; "
                    f"Thorough raises REASONING_EFFORT and opts for a more precise model "
                    f"({model_config.REASONING_MODEL} with {model_config.O4_MINI}/{model_config.O3} fallback)."
                ),
            )
        )

        st_module.session_state[StateKeys.EXTRACTION_STRICT_FORMAT] = True
        st_module.session_state[UIKeys.EXTRACTION_STRICT_FORMAT] = True

        st_module.divider()
        rerun_help = tr(
            "Starte die Extraktion mit den aktuellen Einstellungen neu – praktisch nach einem Sprach-Switch.",
            "Re-run extraction with the current settings – useful after switching language.",
        )
        if st_module.button(
            tr("Extraktion jetzt erneut ausführen", "Re-run extraction now"),
            key=UIKeys.EXTRACTION_RERUN,
            type="secondary",
            help=rerun_help,
            use_container_width=True,
        ):
            queue_extraction_rerun()
            st_module.info(
                tr(
                    "Extraktion wird mit den neuen Einstellungen neu gestartet.",
                    "Extraction will restart using the updated settings.",
                )
            )
