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


def test_generate_job_ad_includes_mission_and_culture_de(monkeypatch):
    captured = {}

    def fake_call_chat_api(messages, **kwargs):
        captured["prompt"] = messages[0]["content"]
        return "ok"

    monkeypatch.setattr(openai_utils, "call_chat_api", fake_call_chat_api)

    session = {
        "company.mission": "Weltklasse Produkte bauen",
        "company.culture": "Teamorientiert und offen",
        "lang": "de",
    }

    openai_utils.generate_job_ad(session)
    prompt = captured["prompt"]
    assert "Unternehmensmission: Weltklasse Produkte bauen" in prompt
    assert "Unternehmenskultur: Teamorientiert und offen" in prompt


def test_generate_job_ad_formats_travel_and_remote(monkeypatch):
    prompts: list[str] = []

    def fake_call_chat_api(messages, **kwargs):
        prompts.append(messages[0]["content"])
        return "ok"

    monkeypatch.setattr(openai_utils, "call_chat_api", fake_call_chat_api)

    session_en = {
        "employment.travel_required": True,
        "employment.travel_details": "Occasional (up to 10%)",
        "employment.work_policy": "Hybrid",
        "employment.work_policy_details": "3 days remote",
        "lang": "en",
    }
    openai_utils.generate_job_ad(session_en)
    assert "Travel Requirements: Occasional (up to 10%)" in prompts[0]
    assert "Work Policy: Hybrid (3 days remote)" in prompts[0]

    session_de = {
        "employment.travel_required": True,
        "employment.travel_details": "Gelegentlich (bis zu 10%)",
        "employment.work_policy": "Hybrid",
        "employment.work_policy_details": "3 Tage remote",
        "employment.relocation_support": True,
        "lang": "de",
    }
    openai_utils.generate_job_ad(session_de)
    assert "Reisebereitschaft: Gelegentlich (bis zu 10%)" in prompts[1]
    assert "Arbeitsmodell: Hybrid (3 Tage remote)" in prompts[1]
    assert "Umzugsunterstützung: Ja" in prompts[1]


def test_generate_job_ad_lists_unique_benefits(monkeypatch):
    captured = {}

    def fake_call_chat_api(messages, **kwargs):
        captured["prompt"] = messages[0]["content"]
        return "ok"

    monkeypatch.setattr(openai_utils, "call_chat_api", fake_call_chat_api)

    session = {
        "compensation.benefits": ["Gym membership", "Gym membership", "401(k) match"],
        "lang": "en",
    }

    openai_utils.generate_job_ad(session)
    prompt = captured["prompt"]
    assert "Benefits: Gym membership, 401(k) match" in prompt
