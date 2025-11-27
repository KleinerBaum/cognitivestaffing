"""Model selection component for Streamlit UI."""

from __future__ import annotations

import streamlit as st

from config import models as model_config
from utils.i18n import tr


def model_selector(key: str = "model") -> str:
    """Surface the fixed default model without allowing overrides."""

    resolved = model_config.OPENAI_MODEL
    st.caption(
        tr(
            "Das Basis-Modell ist fest auf %s eingestellt; Overrides aus der UI oder Umgebungsvariablen werden ignoriert."
            % resolved,
            "The base model is locked to %s; UI or environment overrides are ignored." % resolved,
        )
    )
    st.session_state["model_override"] = ""
    st.session_state[key] = resolved
    st.session_state["model"] = resolved
    return resolved
