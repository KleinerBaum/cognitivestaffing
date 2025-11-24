"""Helpers to embed ChatKit widgets inside Streamlit with consistent styling."""

from __future__ import annotations

from typing import cast
from uuid import uuid4

import streamlit as st
import streamlit.components.v1 as components

import config
from utils.i18n import tr

CHATKIT_SCRIPT_URL = "https://chat.openai.com/chatkit/v1.js"
_SCRIPT_FLAG_KEY = "chatkit.script.loaded"


def _font_stack() -> str:
    return "var(--font-family-base, 'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif)"


def inject_chatkit_script() -> None:
    """Load the ChatKit web component script once, using the allow-listed domain key."""

    if not config.CHATKIT_ENABLED or not config.CHATKIT_DOMAIN_KEY:
        return

    if st.session_state.get(_SCRIPT_FLAG_KEY):
        return

    st.session_state[_SCRIPT_FLAG_KEY] = True
    components.html(
        f"""
<script src="{CHATKIT_SCRIPT_URL}" data-openai-domain-key="{config.CHATKIT_DOMAIN_KEY}"></script>
<style>
  openai-chat, openai-chat * {{
    font-family: {_font_stack()} !important;
  }}
  openai-chat {{
    width: 100%;
    color: inherit;
  }}
</style>
        """,
        height=0,
    )


def render_chatkit_widget(
    *,
    workflow_id: str | None,
    conversation_key: str,
    title_md: str,
    description: str | None,
    lang: str,
    height: int = 540,
) -> None:
    """Render an <openai-chat> component with guardrails and shared styling."""

    if not config.CHATKIT_ENABLED:
        st.info(
            tr(
                "ChatKit ist deaktiviert. Aktiviere CHATKIT_ENABLED, um den Assistenten zu nutzen.",
                "ChatKit is disabled. Enable CHATKIT_ENABLED to use the assistant.",
                lang=lang,
            ),
            icon="ℹ️",
        )
        return

    if not config.CHATKIT_DOMAIN_KEY:
        st.warning(
            tr(
                "ChatKit benötigt einen Domain-Key (CHATKIT_DOMAIN_KEY), damit das Widget geladen wird.",
                "ChatKit needs a domain key (CHATKIT_DOMAIN_KEY) so the widget can load.",
                lang=lang,
            ),
            icon="⚠️",
        )
        return

    if not workflow_id:
        st.warning(
            tr(
                "Kein Workflow hinterlegt – bitte eine Workflow-ID für diesen Assistenten setzen.",
                "No workflow configured — please provide a workflow ID for this assistant.",
                lang=lang,
            ),
            icon="⚠️",
        )
        return

    inject_chatkit_script()

    session_key = f"chatkit.conversation.{conversation_key}"
    conversation_id = cast(str, st.session_state.get(session_key) or uuid4().hex)
    st.session_state[session_key] = conversation_id

    st.markdown(title_md)
    if description:
        st.caption(description)

    components.html(
        f"""
<div class="chatkit-card">
  <openai-chat workflow-id="{workflow_id}" conversation-id="{conversation_id}"></openai-chat>
</div>
<style>
  .chatkit-card {{
    border: 1px solid var(--border-subtle, rgba(95, 210, 255, 0.24));
    background: var(--surface-1, #0a1730);
    border-radius: var(--radius-md, 18px);
    padding: 12px;
  }}
  .chatkit-card openai-chat {{
    min-height: 320px;
  }}
</style>
        """,
        height=height,
    )
