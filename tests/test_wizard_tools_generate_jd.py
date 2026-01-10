from __future__ import annotations

import json
from typing import Any

from wizard_tools import vacancy


def test_generate_jd_uses_job_description_service(monkeypatch: Any) -> None:
    def fake_generate_job_description(
        profile_json: dict[str, Any],
        *,
        tone: str,
        lang: str,
    ) -> dict[str, Any]:
        return {
            "drafts": [
                {"kind": "short", "text": "Short draft", "lang": lang},
                {"kind": "long", "text": "Long draft", "lang": lang},
            ],
            "target_audience": "General candidates",
        }

    monkeypatch.setattr(vacancy, "generate_job_description", fake_generate_job_description)

    payload = json.loads(vacancy.generate_jd({"position": {"job_title": "Analyst"}}, tone="formal", lang="en"))

    assert payload["drafts"][0]["text"] == "Short draft"
    assert payload["drafts"][1]["text"] == "Long draft"
    assert payload["target_audience"] == "General candidates"
