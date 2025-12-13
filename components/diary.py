"""Render a bilingual diary template with OneDrive export controls."""

from __future__ import annotations

from uuid import uuid4
import os

import streamlit as st

from utils.diary import (
    DEFAULT_DIARY_FIELDS,
    DEFAULT_SHARED_URL,
    DiaryEntry,
    build_share_upload_url,
    create_diary_entry,
    upload_markdown_to_onedrive,
)
from utils.i18n import tr

ENTRY_STATE_KEY = "diary.entries"
SHARED_URL_STATE_KEY = "diary.shared_url"
ACCESS_TOKEN_STATE_KEY = "diary.access_token"
DEFAULT_ACCESS_TOKEN = os.getenv("ONEDRIVE_ACCESS_TOKEN") or os.getenv("DIARY_ONEDRIVE_ACCESS_TOKEN", "")


def _ensure_diary_entries() -> list[DiaryEntry]:
    """Guarantee a mutable list of diary entries in the session state."""

    entries = st.session_state.get(ENTRY_STATE_KEY)
    if not isinstance(entries, list):
        st.session_state[ENTRY_STATE_KEY] = []
    return st.session_state[ENTRY_STATE_KEY]


def _new_entry() -> DiaryEntry:
    """Create a new entry with a UUID and today's date."""

    return create_diary_entry(entry_id=str(uuid4()))


def _inject_default_state(shared_url: str) -> None:
    """Initialize shared-link and token fields without overriding user input."""

    st.session_state.setdefault(SHARED_URL_STATE_KEY, shared_url)
    st.session_state.setdefault(ACCESS_TOKEN_STATE_KEY, DEFAULT_ACCESS_TOKEN)


def _sync_entry_values(entry: DiaryEntry, container_key: str) -> None:
    """Wire Streamlit widgets to the entry values while preserving state."""

    entry.entry_date = st.date_input(
        tr("Datum", "Date"),
        value=entry.entry_date,
        key=f"{container_key}.date",
        format="YYYY-MM-DD",
    )

    for field in DEFAULT_DIARY_FIELDS:
        widget_key = f"{container_key}.{field['key']}"
        st.session_state.setdefault(widget_key, entry.values.get(field["key"], ""))
        updated_value = st.text_area(
            f"{field['label_de']} / {field['label_en']}",
            value=st.session_state[widget_key],
            key=widget_key,
            help=f"{field['prompt_de']} / {field['prompt_en']}",
            placeholder=f"{field['prompt_de']} / {field['prompt_en']}",
            height=120,
        )
        entry.values[field["key"]] = updated_value


def _render_entry_actions(
    *,
    entry: DiaryEntry,
    markdown: str,
    shared_url: str,
    access_token: str,
    container_key: str,
) -> None:
    """Show download and OneDrive upload buttons for an entry."""

    filename = f"tagebuch-{entry.entry_date.isoformat()}-{entry.entry_id[:8]}.md"
    columns = st.columns(3)
    columns[0].download_button(
        label=tr("Als Markdown herunterladen", "Download as Markdown"),
        file_name=filename,
        mime="text/markdown",
        data=markdown,
        key=f"{container_key}.download",
    )

    try:
        target_path = f"`{build_share_upload_url(shared_url, filename)}`"
    except ValueError:
        target_path = tr(
            "Freigabelink fehlt – bitte oben eintragen.",
            "Shared link missing – please add it above.",
        )

    columns[1].markdown(
        target_path,
        help=tr(
            "Zielpfad für den Upload (Microsoft Graph Share API).",
            "Target path for the upload (Microsoft Graph Share API).",
        ),
    )

    trigger_key = f"{container_key}.upload"
    if columns[2].button(tr("Nach OneDrive speichern", "Save to OneDrive"), key=trigger_key):
        try:
            upload_markdown_to_onedrive(
                markdown,
                shared_url=shared_url,
                access_token=access_token,
                filename=filename,
            )
        except ValueError as missing:
            st.error(
                tr(
                    f"Upload abgebrochen: {missing}",
                    f"Upload aborted: {missing}",
                )
            )
        except Exception as exc:  # pragma: no cover - defensive UI messaging
            st.error(
                tr(
                    "Upload fehlgeschlagen. Bitte Link, Token oder Verbindung prüfen.",
                    "Upload failed. Please verify the link, token, or connection.",
                )
            )
            st.caption(str(exc))
        else:
            st.success(
                tr(
                    "✅ Eintrag in OneDrive gespeichert.",
                    "✅ Entry saved to OneDrive.",
                )
            )


def render_diary_template() -> None:
    """Render the diary template UI and export controls."""

    _inject_default_state(DEFAULT_SHARED_URL)

    st.header(tr("Tagebuch-Template", "Diary template"))
    st.caption(
        tr(
            "Neue Einträge orientieren sich an deinem handschriftlichen Layout (Tagesleistungen, Reaktionen, Dankbarkeit, Fokus).",
            "New entries mirror your handwritten layout (achievements, reactions, gratitude, focus).",
        )
    )

    with st.expander(tr("OneDrive-Speicher konfigurieren", "Configure OneDrive storage"), expanded=False):
        st.text_input(
            tr("Freigabelink", "Shared link"),
            key=SHARED_URL_STATE_KEY,
            help=tr(
                "Öffentlicher Freigabelink des Zielordners (z. B. OneDrive).",
                "Public share link of the target folder (e.g., OneDrive).",
            ),
        )
        st.text_input(
            tr("Zugriffstoken (Graph API)", "Access token (Graph API)"),
            key=ACCESS_TOKEN_STATE_KEY,
            type="password",
            help=tr(
                "Token sicher z. B. über die Azure-CLI erzeugen und nicht im Klartext speichern.",
                "Provide a temporary Microsoft Graph token; do not store it in plain text.",
            ),
        )
        st.caption(
            tr(
                "Fällt kein Token an, erzeugt die Schaltfläche nur die Markdown-Datei zum manuellen Upload.",
                "If no token is available, the button still produces the Markdown for manual upload.",
            )
        )

    entries = _ensure_diary_entries()
    if not entries:
        entries.append(_new_entry())

    if st.button(tr("Neuen Tages-Eintrag hinzufügen", "Add a new daily entry")):
        entries.append(_new_entry())
        st.toast(tr("Vorlage hinzugefügt.", "Template added."))

    shared_url = str(st.session_state.get(SHARED_URL_STATE_KEY) or DEFAULT_SHARED_URL)
    access_token = str(st.session_state.get(ACCESS_TOKEN_STATE_KEY) or "")

    for index, entry in enumerate(entries, start=1):
        container_key = f"entry-{entry.entry_id}"
        with st.expander(
            tr(
                f"Eintrag {index} – {entry.entry_date.isoformat()}",
                f"Entry {index} – {entry.entry_date.isoformat()}",
            ),
            expanded=index == len(entries),
        ):
            _sync_entry_values(entry, container_key)
            markdown = entry.to_markdown(DEFAULT_DIARY_FIELDS)
            st.markdown(tr("**Vorschau (Markdown)**", "**Preview (Markdown)**"))
            st.code(markdown, language="markdown")
            _render_entry_actions(
                entry=entry,
                markdown=markdown,
                shared_url=shared_url,
                access_token=access_token,
                container_key=container_key,
            )
