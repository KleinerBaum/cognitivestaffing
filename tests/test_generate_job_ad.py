from types import SimpleNamespace

import openai_utils
from openai_utils import ChatCallResult


def test_generate_job_ad_includes_optional_fields(monkeypatch):
    captured = {}

    def fake_call_chat_api(messages, **kwargs):
        captured["prompt"] = messages[0]["content"]
        return ChatCallResult("ok", [], {})

    monkeypatch.setattr(openai_utils.api, "call_chat_api", fake_call_chat_api)

    session = {
        "position": {
            "job_title": "Software Engineer",
            "role_summary": "Build web apps",
            "team_size": 5,
        },
        "company": {
            "name": "Acme Corp",
            "mission": "Build the future of collaboration",
            "culture": "Inclusive and growth-oriented",
        },
        "location": {"primary_city": "Berlin"},
        "responsibilities": {"items": ["Develop features"]},
        "requirements": {"hard_skills_required": ["Python experience"]},
        "employment": {
            "work_policy": "Remote",
            "work_schedule": "Mon-Fri",
            "relocation_support": True,
            "visa_sponsorship": True,
        },
        "compensation": {
            "benefits": ["Stock options"],
            "salary_provided": True,
            "salary_min": 50000,
            "salary_max": 70000,
            "currency": "EUR",
            "period": "year",
        },
        "lang": "en",
    }

    openai_utils.generate_job_ad(
        session,
        selected_fields=[
            "position.job_title::0",
            "company.name::0",
            "location.primary_city::0",
            "position.role_summary::0",
            "responsibilities.items::0",
            "requirements.hard_skills_required::0",
            "employment.work_policy::0",
            "employment.work_schedule::0",
            "employment.relocation_support::0",
            "employment.visa_sponsorship::0",
            "position.team_size::0",
            "compensation.salary::0",
            "compensation.benefits::0",
        ],
        target_audience="Experienced engineers",
        manual_sections=[],
        lang="en",
        selected_values={
            "position.job_title::0": "Software Engineer",
            "company.name::0": "Acme Corp",
            "location.primary_city::0": "Berlin",
            "position.role_summary::0": "Build web apps",
            "responsibilities.items::0": "Develop features",
            "requirements.hard_skills_required::0": "Python experience",
            "employment.work_policy::0": "Remote",
            "employment.work_schedule::0": "Mon-Fri",
            "employment.relocation_support::0": True,
            "employment.visa_sponsorship::0": True,
            "position.team_size::0": 5,
            "compensation.salary::0": "50,000–70,000 EUR / year",
            "compensation.benefits::0": "Stock options",
        },
    )
    prompt = captured["prompt"]
    assert "Relevant information:" in prompt
    assert "Job Title: Software Engineer" in prompt
    assert "Company: Acme Corp" in prompt
    assert "Location: Berlin" in prompt
    assert "Role Summary: Build web apps" in prompt
    assert "Key Responsibilities: Develop features" in prompt
    assert "Hard Skills (Must-have): Python experience" in prompt
    assert "Work Policy: Remote" in prompt
    assert "Work Schedule: Mon-Fri" in prompt
    assert "Relocation Support: Yes" in prompt
    assert "Visa Sponsorship: Yes" in prompt
    assert "Team Size: 5" in prompt
    assert "Salary Range: 50,000–70,000 EUR / year" in prompt
    assert "Benefits: Stock options" in prompt
    assert "Target audience: Experienced engineers" in prompt


def test_generate_job_ad_includes_mission_and_culture_de(monkeypatch):
    captured = {}

    def fake_call_chat_api(messages, **kwargs):
        captured["prompt"] = messages[0]["content"]
        return ChatCallResult("ok", [], {})

    monkeypatch.setattr(openai_utils.api, "call_chat_api", fake_call_chat_api)

    session = {
        "company": {
            "mission": "Weltklasse Produkte bauen",
            "culture": "Teamorientiert und offen",
        },
        "lang": "de",
    }

    openai_utils.generate_job_ad(
        session,
        selected_fields=["company.mission::0", "company.culture::0"],
        target_audience="Talente mit Teamgeist",
        manual_sections=[],
        selected_values={
            "company.mission::0": "Weltklasse Produkte bauen",
            "company.culture::0": "Teamorientiert und offen",
        },
    )
    prompt = captured["prompt"]
    assert "Relevante Informationen:" in prompt
    assert "Mission: Weltklasse Produkte bauen" in prompt
    assert "Kultur: Teamorientiert und offen" in prompt
    assert "Zielgruppe: Talente mit Teamgeist" in prompt


def test_generate_job_ad_formats_travel_and_remote(monkeypatch):
    prompts: list[str] = []

    def fake_call_chat_api(messages, **kwargs):
        prompts.append(messages[0]["content"])
        return ChatCallResult("ok", [], {})

    monkeypatch.setattr(openai_utils.api, "call_chat_api", fake_call_chat_api)

    session_en = {
        "employment": {
            "travel_required": True,
            "travel_details": "Occasional (up to 10%)",
            "work_policy": "Hybrid",
        },
        "lang": "en",
    }
    openai_utils.generate_job_ad(
        session_en,
        selected_fields=[
            "employment.travel_required",
            "employment.work_policy",
        ],
        target_audience="Hybrid workers",
        manual_sections=[],
    )
    assert "Travel Requirements: Occasional (up to 10%)" in prompts[0]
    assert "Work Policy: Hybrid" in prompts[0]

    session_de = {
        "employment": {
            "travel_required": True,
            "travel_details": "Gelegentlich (bis zu 10%)",
            "work_policy": "Hybrid",
            "work_policy_details": "3 Tage remote",
            "relocation_support": True,
        },
        "lang": "de",
    }
    openai_utils.generate_job_ad(
        session_de,
        selected_fields=[
            "employment.travel_required",
            "employment.work_policy",
            "employment.relocation_support",
        ],
        target_audience="Flexibel arbeitende Talente",
        manual_sections=[],
    )
    assert "Reisebereitschaft: Gelegentlich (bis zu 10%)" in prompts[1]
    assert "Arbeitsmodell: Hybrid (3 Tage remote)" in prompts[1]
    assert "Umzugsunterstützung: Ja" in prompts[1]


def test_generate_job_ad_uses_remote_percentage(monkeypatch):
    prompts: list[str] = []

    def fake_call_chat_api(messages, **kwargs):
        prompts.append(messages[0]["content"])
        return ChatCallResult("ok", [], {})

    monkeypatch.setattr(openai_utils.api, "call_chat_api", fake_call_chat_api)

    session = {
        "employment": {"work_policy": "Hybrid", "remote_percentage": 60},
        "lang": "en",
    }
    openai_utils.generate_job_ad(
        session,
        selected_fields=["employment.work_policy"],
        target_audience="Remote minded",
        manual_sections=[],
    )
    assert "Work Policy: Hybrid (60% remote)" in prompts[0]


def test_generate_job_ad_lists_unique_benefits(monkeypatch):
    captured = {}

    def fake_call_chat_api(messages, **kwargs):
        captured["prompt"] = messages[0]["content"]
        return ChatCallResult("ok", [], {})

    monkeypatch.setattr(openai_utils.api, "call_chat_api", fake_call_chat_api)

    session = {
        "compensation": {
            "benefits": ["Gym membership", "Gym membership", "401(k) match"],
            "salary_provided": False,
        },
        "lang": "en",
    }

    openai_utils.generate_job_ad(
        session,
        selected_fields=["compensation.benefits"],
        target_audience="Benefit seekers",
        manual_sections=[],
    )
    prompt = captured["prompt"]
    assert "Benefits: Gym membership, 401(k) match" in prompt


def test_generate_job_ad_includes_manual_sections(monkeypatch):
    captured = {}

    def fake_call_chat_api(messages, **kwargs):
        captured["prompt"] = messages[0]["content"]
        return ChatCallResult("ok", [], {})

    monkeypatch.setattr(openai_utils.api, "call_chat_api", fake_call_chat_api)

    session = {
        "position": {"job_title": "Product Manager"},
        "lang": "en",
    }

    openai_utils.generate_job_ad(
        session,
        selected_fields=["position.job_title"],
        target_audience="Experienced talent",
        manual_sections=[
            {"title": "Culture", "content": "We value openness."},
            {"content": "Flexible working hours."},
        ],
    )

    prompt = captured["prompt"]
    assert "Culture: We value openness." in prompt
    assert "Flexible working hours." in prompt


def test_generate_job_ad_uses_output_fallback(monkeypatch):
    class StubResponse:
        def __init__(self, text: str) -> None:
            self.output_text = None
            self.output = [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": text}],
                }
            ]
            self.usage = {"input_tokens": 0, "output_tokens": 0}

    stub_text = "Generated job ad"
    stub_response = StubResponse(stub_text)

    monkeypatch.setattr("core.analysis_tools.build_analysis_tools", lambda: ([], {}))

    dummy_streamlit = SimpleNamespace(
        session_state={},
        error=lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(openai_utils.api, "st", dummy_streamlit)
    monkeypatch.setattr(
        openai_utils.api, "_execute_response", lambda *_args, **_kwargs: stub_response
    )
    monkeypatch.setattr(openai_utils.api, "client", None)

    result = openai_utils.generate_job_ad(
        {"lang": "en", "position": {"job_title": "QA Engineer"}},
        selected_fields=["position.job_title"],
        target_audience="Quality engineers",
        manual_sections=[],
    )

    assert result == stub_text
