import openai_utils


def test_generate_job_ad_includes_optional_fields(monkeypatch):
    captured = {}

    def fake_call_chat_api(messages, **kwargs):
        captured["prompt"] = messages[0]["content"]
        return "ok"

    monkeypatch.setattr(openai_utils, "call_chat_api", fake_call_chat_api)

    session = {
        "job_title": "Software Engineer",
        "company_name": "Acme Corp",
        "location": "Berlin",
        "role_summary": "Build web apps",
        "tasks": "Develop features",
        "benefits": "Stock options",
        "qualifications": "Python experience",
        "remote_policy": "Remote-friendly",
        "salary_range": "€50k-70k",
        "lang": "en",
    }

    openai_utils.generate_job_ad(session)
    prompt = captured["prompt"]
    assert "Requirements: Python experience" in prompt
    assert "Work Policy: Remote-friendly" in prompt
    assert "Salary Range: €50k-70k" in prompt
