from __future__ import annotations

from typing import Any

from wizard.services import job_description


def test_generate_job_description_builds_short_and_long_drafts(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    def fake_generate_job_ad(
        session_data: dict[str, Any],
        selected_fields: list[str],
        *,
        target_audience: str,
        tone: str,
        lang: str,
        **_: Any,
    ) -> str:
        captured["target_audience"] = target_audience
        captured["tone"] = tone
        captured["lang"] = lang
        captured["selected_fields"] = selected_fields
        return "Long draft " + "word " * 120

    monkeypatch.setattr(job_description, "generate_job_ad", fake_generate_job_ad)

    result = job_description.generate_job_description(
        {"position": {"job_title": "Data Engineer"}},
        tone="friendly",
        lang="de",
    )

    assert captured["target_audience"] == "Kandidat:innen für Data Engineer"
    assert captured["tone"] == "friendly"
    assert captured["lang"] == "de"
    assert "position.job_title" in captured["selected_fields"]

    drafts = result["drafts"]
    assert drafts[0]["kind"] == "short"
    assert drafts[1]["kind"] == "long"
    assert drafts[0]["text"].endswith("…")
