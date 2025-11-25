from pipelines.need_analysis import extract_need_analysis_profile
from utils.json_repair import JsonRepairStatus


def test_pipeline_repairs_invalid_json(monkeypatch):
    invalid_json = '{"position": {"job_title": "Engineer",}}'
    from llm.json_repair import parse_profile_json

    def fake_parse_structured_payload(raw: str, *, source_text: str | None = None):
        result = parse_profile_json(raw)
        payload = result.payload or {}
        return payload, result.status is JsonRepairStatus.REPAIRED, list(result.issues)

    def fake_extract_json(*_: object, **__: object) -> str:
        return invalid_json

    monkeypatch.setattr("llm.json_repair.is_llm_enabled", lambda: False)
    monkeypatch.setattr("pipelines.need_analysis.parse_structured_payload", fake_parse_structured_payload)
    monkeypatch.setattr("pipelines.need_analysis.extract_json", fake_extract_json)
    monkeypatch.setattr("llm.client.extract_json", fake_extract_json)

    result = extract_need_analysis_profile("example job ad")

    assert result.recovered is True
    assert result.data["position"]["job_title"] == "Engineer"
    assert any(result.issues)
    assert result.raw_json == invalid_json
