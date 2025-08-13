import openai_utils


def test_generate_job_ad_includes_optional_fields(monkeypatch):
    captured = {}

    def fake_call_chat_api(messages, **kwargs):
        captured["prompt"] = messages[0]["content"]
        return "ok"

    monkeypatch.setattr(openai_utils, "call_chat_api", fake_call_chat_api)

    session = {
        "position.job_title": "Software Engineer",
        "company.name": "Acme Corp",
        "location.primary_city": "Berlin",
        "position.role_summary": "Build web apps",
        "responsibilities.items": ["Develop features"],
        "compensation.benefits": ["Stock options"],
        "learning_opportunities": "Annual training budget",
        "requirements.hard_skills": ["Python experience"],
        "employment.work_policy": "Remote",
        "employment.work_schedule": "Mon-Fri",
        "employment.relocation_support": True,
        "employment.visa_sponsorship": True,
        "position.team_size": 5,
        "compensation.salary_provided": True,
        "compensation.salary_min": 50000,
        "compensation.salary_max": 70000,
        "company.mission": "Build the future of collaboration",
        "company.culture": "Inclusive and growth-oriented",
        "lang": "en",
    }

    openai_utils.generate_job_ad(session, tone="formal and straightforward")
    prompt = captured["prompt"]
    assert "Hard Skills: Python experience" in prompt
    assert "Work Policy: Remote" in prompt
    assert "Work Schedule: Mon-Fri" in prompt
    assert "Relocation Assistance: Yes" in prompt
    assert "Visa Sponsorship: Yes" in prompt
    assert "Learning & Development: Annual training budget" in prompt
    assert "Team Size: 5" in prompt
    assert "Salary Range: 50,000–70,000 EUR per year" in prompt
    assert "Company Mission: Build the future of collaboration" in prompt
    assert "Company Culture: Inclusive and growth-oriented" in prompt
    assert "Tone: formal and straightforward." in prompt
