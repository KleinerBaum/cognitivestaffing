"""Diary helpers for templating and OneDrive uploads.

This module models a bilingual diary entry template (mirroring the
handwritten structure from the provided notebook photos) and offers helper
utilities to turn entries into Markdown as well as upload them to a shared
OneDrive folder.
"""

from __future__ import annotations

import base64
import os
import re
from dataclasses import dataclass, field as dataclass_field
from datetime import date, datetime
from typing import Callable, Sequence

import requests
from requests import Response

DiaryField = dict[str, str]


@dataclass(slots=True)
class DiaryEntry:
    """A structured diary entry with bilingual fields."""

    entry_id: str
    entry_date: date
    created_at: datetime
    values: dict[str, str] = dataclass_field(default_factory=dict)

    def to_markdown(self, fields: Sequence[DiaryField]) -> str:
        """Render the diary entry as Markdown, keeping both DE/EN headings."""

        header = (
            f"# Tagebuch / Journal – {self.entry_date.isoformat()}\n"
            f"_Erstellt um / created at {self.created_at.isoformat(timespec='minutes')}_"
        )
        parts: list[str] = [header, ""]

        for field in fields:
            title = f"{field['label_de']} / {field['label_en']}"
            content = self.values.get(field["key"], "").strip() or "-"
            parts.extend([f"## {title}", content, ""])

        return "\n".join(parts).rstrip()


def _field(key: str, *, label_de: str, label_en: str, prompt_de: str, prompt_en: str) -> DiaryField:
    return {
        "key": key,
        "label_de": label_de,
        "label_en": label_en,
        "prompt_de": prompt_de,
        "prompt_en": prompt_en,
    }


DEFAULT_DIARY_FIELDS: tuple[DiaryField, ...] = (
    _field(
        "achievements",
        label_de="Tagesleistungen",
        label_en="Day achievements",
        prompt_de="Was habe ich heute geschafft?",
        prompt_en="What did I accomplish today?",
    ),
    _field(
        "concerns",
        label_de="Was beschäftigt mich?",
        label_en="What is on my mind?",
        prompt_de="Gedanken, Sorgen oder Konflikte festhalten.",
        prompt_en="Capture thoughts, worries, or conflicts.",
    ),
    _field(
        "reactions",
        label_de="Reaktionen (Körper/Geist)",
        label_en="Reactions (body/mind)",
        prompt_de="Welche körperlichen und geistigen Reaktionen nehme ich wahr?",
        prompt_en="What physical or mental reactions do I notice?",
    ),
    _field(
        "emotions",
        label_de="Bemerke ich Emotionen?",
        label_en="What emotions do I notice?",
        prompt_de="Gefühle konkret benennen (z. B. Traurigkeit, Frust, Anspannung).",
        prompt_en="Name the feelings (e.g., sadness, frustration, tension).",
    ),
    _field(
        "triggers",
        label_de="Auslöser & Reaktionen",
        label_en="Triggers & reactions",
        prompt_de="Welche Situationen oder Personen haben etwas ausgelöst?",
        prompt_en="Which situations or people triggered reactions?",
    ),
    _field(
        "positives",
        label_de="Positives & Dankbarkeit",
        label_en="Positive moments & gratitude",
        prompt_de="3 Dinge, für die ich heute dankbar bin oder die gut liefen.",
        prompt_en="Three things that went well or I am grateful for today.",
    ),
    _field(
        "thought_challenge",
        label_de="Gedanken-Challenge",
        label_en="Thought challenge",
        prompt_de="Welche Gedanken möchte ich hinterfragen oder neu bewerten?",
        prompt_en="Which thoughts should I challenge or reframe?",
    ),
    _field(
        "activities",
        label_de="Aktivitäten & Energie",
        label_en="Activities & energy",
        prompt_de="Welche Aktivitäten haben Energie gegeben oder gezogen?",
        prompt_en="Which activities added or drained energy?",
    ),
    _field(
        "self_care",
        label_de="Selbstfürsorge",
        label_en="Self-care",
        prompt_de="Was habe ich heute für mich getan?",
        prompt_en="What did I do for self-care today?",
    ),
    _field(
        "improvement",
        label_de="Was morgen besser machen",
        label_en="What to improve tomorrow",
        prompt_de="Konkrete Schritte, die morgen leichter oder besser laufen sollen.",
        prompt_en="Concrete steps to make tomorrow smoother or better.",
    ),
    _field(
        "next_focus",
        label_de="Morgen-Fokus",
        label_en="Focus for tomorrow",
        prompt_de="1–2 Prioritäten oder Pläne für den nächsten Tag formulieren.",
        prompt_en="Outline 1–2 priorities or plans for the next day.",
    ),
)


DEFAULT_SHARED_URL = os.getenv(
    "DIARY_ONEDRIVE_SHARED_URL",
    "https://1drv.ms/f/c/497745699E449E1E/IgChcvff4KYxTLfhBTO8z6LMAYTUfTRfvB4L0Z_FFRhALkw?e=vGH37a",
)


def create_diary_entry(entry_id: str, *, entry_date: date | None = None) -> DiaryEntry:
    """Instantiate a new diary entry populated with empty fields."""

    base_values = {field["key"]: "" for field in DEFAULT_DIARY_FIELDS}
    today = entry_date or date.today()
    return DiaryEntry(
        entry_id=entry_id,
        entry_date=today,
        created_at=datetime.now(),
        values=base_values,
    )


def build_share_upload_url(shared_url: str, filename: str) -> str:
    """Create the Microsoft Graph upload URL for a share link and filename."""

    normalized_share = shared_url.strip()
    normalized_filename = re.sub(r"[^A-Za-z0-9._-]", "_", filename.strip())
    if not normalized_share:
        raise ValueError("A shared URL is required to build the upload path.")
    if not normalized_filename:
        raise ValueError("A filename is required to build the upload path.")

    encoded = base64.urlsafe_b64encode(normalized_share.encode("utf-8")).decode("ascii")
    resource_id = encoded.rstrip("=")
    return f"https://graph.microsoft.com/v1.0/shares/u!{resource_id}/driveItem:/{normalized_filename}:/content"


def upload_markdown_to_onedrive(
    markdown: str,
    *,
    shared_url: str,
    access_token: str,
    filename: str,
    request_func: Callable[..., Response] | None = None,
    timeout: float = 10.0,
) -> Response:
    """Upload the provided Markdown to OneDrive using the shared link.

    The `request_func` parameter allows dependency injection for unit tests.
    A ValueError is raised for missing inputs; HTTP errors propagate via a
    RuntimeError containing the response status and text so the caller can
    show a friendly UI hint.
    """

    if not shared_url.strip():
        raise ValueError("shared_url is required for the OneDrive upload.")
    if not access_token.strip():
        raise ValueError("access_token is required for the OneDrive upload.")

    upload_url = build_share_upload_url(shared_url, filename)
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "text/markdown",
    }
    request = request_func or requests.put
    response = request(upload_url, data=markdown.encode("utf-8"), headers=headers, timeout=timeout)
    if response.status_code >= 400:
        raise RuntimeError(f"OneDrive upload failed ({response.status_code}): {response.text}")
    return response
