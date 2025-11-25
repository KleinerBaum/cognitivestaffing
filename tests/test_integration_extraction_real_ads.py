from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

import pytest

from ingest.types import build_plain_text_document
from llm.client import StructuredExtractionOutcome
from models.need_analysis import NeedAnalysisProfile, Requirements
from pipelines.need_analysis import ExtractionResult, extract_need_analysis_profile


@dataclass
class SampleJobAd:
    name: str
    fixture: Path
    marker: str
    payload: dict[str, Any]
    expectations: Mapping[str, str]
    company_hint: str | None = None
    title_hint: str | None = None

    @property
    def text(self) -> str:
        return self.fixture.read_text(encoding="utf-8")


def _load_fixture(filename: str) -> Path:
    base = Path(__file__).resolve().parent / "fixtures" / "job_ads"
    return base / filename


@pytest.fixture
def sample_job_ads() -> list[SampleJobAd]:
    return [
        SampleJobAd(
            name="produktentwickler_mobilitaet",
            fixture=_load_fixture("produktentwickler_mobilitaet_de.txt"),
            marker="MoveNow GmbH",
            company_hint="MoveNow GmbH",
            title_hint="Produktentwickler Mobilität",
            payload={
                "company": {
                    "name": "MoveNow GmbH",
                    "description": "Start-up für On-Demand-Mobilität",
                    "benefits": [
                        "Deutschlandticket",
                        "Mobilitätsbudget",
                        "Weiterbildungsbudget",
                    ],
                },
                "position": {
                    "job_title": "Produktentwickler innovative Mobilitätskonzepte",
                    "role_summary": "Entwicklung von Prototypen für On-Demand-Mobilität und Shuttle-Services",
                    "team_structure": "Cross-funktionales Team mit UX, Data und Betrieb",
                    "reporting_line": "Berichtet an den CTO",
                },
                "department": {"name": "Produktentwicklung"},
                "team": {
                    "mission": "Wir testen neue Mobilitätsangebote in deutschen Großstädten",
                    "headcount_current": 8,
                    "collaboration_tools": "Jira, Miro",
                },
                "location": {
                    "primary_city": "Berlin",
                    "country": "Germany",
                    "onsite_ratio": "Hybrid",
                },
                "responsibilities": {
                    "items": [
                        "Prototypen für On-Demand-Mobilität und Shuttle-Services entwickeln",
                        "Mit UX, Data und Betriebsteam Roadmap priorisieren",
                        "Fahrgastfeedback auswerten und Features testen",
                    ]
                },
                "requirements": {
                    "hard_skills_required": [
                        "Fahrzeugtechnik",
                        "Service Design",
                    ],
                    "soft_skills_required": [
                        "Stakeholder-Management",
                        "Analytisches Denken",
                    ],
                    "languages_required": ["Deutsch (C1)", "Englisch (B2)"],
                    "certificates": ["Fahrerlaubnis Klasse B"],
                },
                "employment": {
                    "job_type": "Vollzeit",
                    "work_policy": "Hybrid",
                    "contract_type": "Unbefristet",
                },
                "compensation": {
                    "salary_provided": True,
                    "salary_min": 65000,
                    "salary_max": 80000,
                    "currency": "EUR",
                    "period": "year",
                    "benefits": [
                        "Deutschlandticket",
                        "Mobilitätsbudget",
                        "30 Tage Urlaub",
                    ],
                },
                "process": {
                    "hiring_process": [
                        "Telefoninterview mit Recruiting",
                        "Case Study mit dem Produktteam",
                        "Gespräch mit dem CTO vor Ort",
                    ],
                    "recruitment_timeline": "4 Wochen",
                },
                "meta": {},
            },
            expectations={
                "responsibility_phrase": "On-Demand-Mobilität",
                "requirement_phrase": "Fahrzeugtechnik",
                "benefit_phrase": "Deutschlandticket",
                "process_phrase": "Case Study",
            },
        ),
        SampleJobAd(
            name="talent_strategy_manager",
            fixture=_load_fixture("talent_strategy_manager_en.txt"),
            marker="Accelor Partners",
            company_hint="Accelor Partners",
            title_hint="Talent & Organization Strategy Manager",
            payload={
                "company": {
                    "name": "Accelor Partners",
                    "description": "Strategy consultancy supporting enterprise transformations",
                    "benefits": [
                        "Annual bonus",
                        "Learning stipend",
                        "Hybrid work",
                    ],
                },
                "position": {
                    "job_title": "Talent & Organization Strategy Manager",
                    "role_summary": "Lead transformation workstreams and design talent strategies",
                    "reporting_line": "Reports to the strategy lead",
                },
                "department": {"name": "Transformation"},
                "team": {
                    "mission": "Partner with clients on organization and talent strategy",
                    "locations": "Munich",
                },
                "location": {
                    "primary_city": "Munich",
                    "country": "Germany",
                    "onsite_ratio": "Hybrid",
                },
                "responsibilities": {
                    "items": [
                        "Lead transformation workstreams with enterprise clients",
                        "Design operating models, talent strategies, and change roadmaps",
                        "Coach client teams and facilitate executive workshops",
                    ]
                },
                "requirements": {
                    "hard_skills_required": [
                        "Org design",
                        "Workforce planning",
                    ],
                    "soft_skills_required": [
                        "Facilitation",
                        "Executive communication",
                    ],
                    "languages_required": ["English (fluent)", "German (B2)"],
                },
                "employment": {
                    "job_type": "Full-time",
                    "work_policy": "Hybrid",
                },
                "compensation": {
                    "salary_provided": True,
                    "salary_min": 90000,
                    "salary_max": 110000,
                    "currency": "EUR",
                    "period": "year",
                    "benefits": [
                        "Annual bonus",
                        "Learning stipend",
                        "30 days vacation",
                    ],
                },
                "process": {
                    "hiring_process": [
                        "Recruiter screen",
                        "Case interview with the strategy lead",
                        "Executive panel",
                    ],
                    "interview_stages": 3,
                },
                "meta": {},
            },
            expectations={
                "responsibility_phrase": "transformation workstreams",
                "requirement_phrase": "Workforce planning",
                "benefit_phrase": "Annual bonus",
                "process_phrase": "Executive panel",
            },
        ),
        SampleJobAd(
            name="senior_backend_engineer",
            fixture=_load_fixture("senior_backend_engineer_en.txt"),
            marker="Northwind Logistics",
            company_hint="Northwind Logistics",
            title_hint="Senior Backend Engineer",
            payload={
                "company": {
                    "name": "Northwind Logistics",
                    "description": "Logistics scale-up focused on real-time parcel tracking",
                    "benefits": [
                        "Equity",
                        "On-call allowance",
                        "Health add-ons",
                    ],
                },
                "position": {
                    "job_title": "Senior Backend Engineer",
                    "role_summary": "Build scalable APIs and improve reliability for parcel routing",
                    "reporting_line": "Reports to the Head of Engineering",
                },
                "department": {"name": "Platform Engineering"},
                "team": {
                    "mission": "Enable parcel routing and tracking with reliable services",
                    "locations": "Hamburg / remote in Germany",
                },
                "location": {
                    "primary_city": "Hamburg",
                    "country": "Germany",
                    "onsite_ratio": "Remote-friendly",
                },
                "responsibilities": {
                    "items": [
                        "Build scalable APIs for parcel routing and tracking",
                        "Improve reliability and monitoring for Go services",
                        "Partner with product to design roadmap experiments",
                    ]
                },
                "requirements": {
                    "hard_skills_required": [
                        "Go",
                        "Python",
                        "Cloud-native architectures",
                    ],
                    "soft_skills_required": [
                        "Mentoring",
                        "Collaboration with operations",
                    ],
                    "languages_required": ["English"],
                },
                "employment": {
                    "job_type": "Full-time",
                    "work_policy": "Remote-friendly",
                },
                "compensation": {
                    "salary_provided": True,
                    "salary_min": 80000,
                    "salary_max": 95000,
                    "currency": "EUR",
                    "period": "year",
                    "benefits": [
                        "Equity",
                        "On-call allowance",
                        "Equipment budget",
                    ],
                },
                "process": {
                    "hiring_process": [
                        "Intro call",
                        "Technical pairing session",
                        "Architecture interview",
                        "Founder chat",
                    ],
                },
                "meta": {},
            },
            expectations={
                "responsibility_phrase": "parcel routing",
                "requirement_phrase": "Cloud-native",
                "benefit_phrase": "Equity",
                "process_phrase": "Architecture interview",
            },
        ),
    ]


def _assert_non_empty(values: Iterable[str]) -> None:
    for value in values:
        assert value.strip(), "Expected non-empty value"


@pytest.fixture(autouse=True)
def disable_llm_repairs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("llm.json_repair.is_llm_enabled", lambda: False)
    monkeypatch.setattr("config.is_llm_enabled", lambda: False)


def _collect_requirements(requirements: Requirements) -> list[str]:
    return [
        *requirements.hard_skills_required,
        *requirements.hard_skills_optional,
        *requirements.soft_skills_required,
        *requirements.soft_skills_optional,
        *requirements.tools_and_technologies,
        *requirements.languages_required,
        *requirements.languages_optional,
        *requirements.certificates,
        *requirements.certifications,
    ]


@pytest.fixture(autouse=True)
def mock_structured_extraction(monkeypatch: pytest.MonkeyPatch, sample_job_ads: list[SampleJobAd]):
    def _fake_extract_json_outcome(
        text: str,
        title: str | None = None,
        company: str | None = None,
        url: str | None = None,
        locked_fields: Mapping[str, str] | None = None,
        *,
        minimal: bool = False,
    ) -> StructuredExtractionOutcome:
        for ad in sample_job_ads:
            if ad.marker in text:
                return StructuredExtractionOutcome(
                    content=json.dumps(ad.payload, ensure_ascii=False),
                    source=f"mock::{ad.name}",
                )
        raise AssertionError(f"Unexpected extraction call for text: {text[:80]}")

    monkeypatch.setattr("pipelines.need_analysis._extract_json_outcome", _fake_extract_json_outcome)


def test_real_job_ads_produce_rich_profiles(sample_job_ads: list[SampleJobAd]):
    for ad in sample_job_ads:
        doc = build_plain_text_document(ad.text, source=ad.name)

        result: ExtractionResult = extract_need_analysis_profile(
            doc.text,
            title_hint=ad.title_hint,
            company_hint=ad.company_hint,
        )

        profile = NeedAnalysisProfile.model_validate(result.data)

        assert profile.company.name
        assert profile.position.job_title
        assert profile.position.role_summary
        assert profile.responsibilities.items
        assert profile.compensation.benefits
        assert profile.process.hiring_process

        _assert_non_empty(profile.responsibilities.items)
        _assert_non_empty(profile.compensation.benefits)
        _assert_non_empty(profile.process.hiring_process)

        requirements_values = _collect_requirements(profile.requirements)
        _assert_non_empty(requirements_values)

        responsibilities_text = " ".join(profile.responsibilities.items)
        requirement_text = " ".join(requirements_values)
        benefits_text = " ".join(profile.compensation.benefits)
        process_text = " ".join(profile.process.hiring_process)

        assert ad.expectations["responsibility_phrase"] in responsibilities_text
        assert ad.expectations["requirement_phrase"] in requirement_text
        assert ad.expectations["benefit_phrase"] in benefits_text
        assert ad.expectations["process_phrase"] in process_text
