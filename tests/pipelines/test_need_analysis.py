from __future__ import annotations

import json
from typing import Any, Mapping

import pytest

from models.need_analysis import NeedAnalysisProfile
from pipelines.need_analysis import extract_need_analysis_profile


class _Recorder:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def __call__(
        self,
        text: str,
        *,
        title: str | None = None,
        company: str | None = None,
        url: str | None = None,
        locked_fields: Mapping[str, str] | None = None,
        minimal: bool = False,
    ) -> str:
        self.calls.append(
            {
                "text": text,
                "title": title,
                "company": company,
                "url": url,
                "locked_fields": dict(locked_fields or {}),
                "minimal": minimal,
            }
        )
        return json.dumps(NeedAnalysisProfile().model_dump())


def test_extract_need_analysis_profile_uses_llm_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = _Recorder()
    monkeypatch.setattr("pipelines.need_analysis.extract_json", recorder)

    result = extract_need_analysis_profile(
        "Senior Engineer role",
        title_hint="Engineer",
        company_hint="Acme",
        url_hint="https://example.com",
        locked_fields={"company.name": "Acme"},
    )

    assert recorder.calls == [
        {
            "text": "Senior Engineer role",
            "title": "Engineer",
            "company": "Acme",
            "url": "https://example.com",
            "locked_fields": {"company.name": "Acme"},
            "minimal": False,
        }
    ]
    assert result.recovered is False
    assert result.issues == []
    assert result.data == NeedAnalysisProfile().model_dump()
    assert json.loads(result.raw_json) == NeedAnalysisProfile().model_dump()
