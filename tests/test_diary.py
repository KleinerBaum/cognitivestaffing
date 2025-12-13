from __future__ import annotations

from datetime import date, datetime
from typing import Any, cast

import pytest
from requests import Response

from utils.diary import (
    DEFAULT_DIARY_FIELDS,
    build_share_upload_url,
    create_diary_entry,
    upload_markdown_to_onedrive,
)


def test_create_diary_entry_populates_all_fields() -> None:
    entry = create_diary_entry("demo", entry_date=date(2024, 1, 1))

    assert entry.entry_date == date(2024, 1, 1)
    assert set(entry.values) == {field["key"] for field in DEFAULT_DIARY_FIELDS}


def test_to_markdown_renders_bilingual_headers() -> None:
    entry = create_diary_entry("demo")
    entry.created_at = datetime(2024, 1, 1, 8, 0)
    entry.values["achievements"] = "Testinhalt"

    markdown = entry.to_markdown(DEFAULT_DIARY_FIELDS)

    assert "Tagebuch / Journal" in markdown
    assert "Day achievements" in markdown
    assert "Testinhalt" in markdown


def test_build_share_upload_url_encodes_link() -> None:
    upload_url = build_share_upload_url("https://example.com/share", "my file.md")

    assert upload_url.startswith("https://graph.microsoft.com/v1.0/shares/u!")
    assert upload_url.endswith("/driveItem:/my_file.md:/content")
    assert " " not in upload_url


def test_upload_uses_injected_request_function() -> None:
    calls: dict[str, Any] = {}

    def fake_put(url: str, data: bytes, headers: dict[str, str], timeout: float) -> Response:
        calls["url"] = url
        calls["data"] = data
        calls["headers"] = headers
        calls["timeout"] = timeout

        response = Response()
        response.status_code = 201
        response._content = b"ok"  # noqa: SLF001 - test-only content mutation
        return response

    response = upload_markdown_to_onedrive(
        "content",
        shared_url="https://example.com/share",
        access_token="token123",
        filename="entry.md",
        request_func=fake_put,
        timeout=5.0,
    )

    headers = cast(dict[str, str], calls["headers"])
    assert isinstance(response, Response)
    assert "Authorization" in headers
    assert calls["timeout"] == 5.0
    assert calls["data"] == b"content"


def test_upload_missing_inputs_raise_value_error() -> None:
    with pytest.raises(ValueError):
        upload_markdown_to_onedrive(
            "content",
            shared_url="",
            access_token="token123",
            filename="entry.md",
        )

    with pytest.raises(ValueError):
        upload_markdown_to_onedrive(
            "content",
            shared_url="https://example.com/share",
            access_token="",
            filename="entry.md",
        )
