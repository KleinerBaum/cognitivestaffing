"""Default payloads and helper factories for the RecruitingWizard schema."""

from __future__ import annotations

from typing import Any, Mapping

from .schema import (
    KEYS_CANONICAL,
    OnCallRequirement,
    RecruitingWizard,
    SourceType,
    WorkModel,
)


_DEFAULT_WIZARD_DATA: Mapping[str, Any] = {
    "company": {
        "name": "Acme Robotics",
        "legal_name": "Acme Robotics GmbH",
        "tagline": "Sustainable automation for modern factories",
        "mission": "Design resilient robotics platforms that shrink downtime and energy waste.",
        "headquarters": "Berlin, Germany",
        "locations": ["Berlin", "Munich"],
        "industries": ["Robotics", "Industrial Automation"],
        "website": "https://careers.acmerobotics.example",
        "values": ["Customer impact", "Safety first", "Inclusive teams"],
    },
    "department": {
        "name": "Platform Engineering",
        "function": "Operate the robotics control plane and observability stack.",
        "leader_name": "Sven Richter",
        "leader_title": "VP Engineering",
        "strategic_goals": [
            "Cut unplanned downtime by 40%",
            "Introduce predictive maintenance analytics",
        ],
    },
    "team": {
        "name": "Control Systems Reliability",
        "mission": "Keep the robotics platform resilient across 24/7 operations.",
        "reporting_line": "Director Platform Engineering",
        "headcount_current": 8,
        "headcount_target": 12,
        "collaboration_tools": ["Slack", "Notion", "PagerDuty"],
        "locations": ["Berlin"],
    },
    "role": {
        "title": "Senior Reliability Engineer",
        "purpose": "Lead reliability initiatives for robotics control services.",
        "outcomes": [
            "Reduce on-call pages by 30% in the first six months",
            "Deliver automated failure testing for every critical service",
        ],
        "employment_type": "full_time",
        "work_model": WorkModel.HYBRID.value,
        "on_call": OnCallRequirement.ROTATION.value,
        "reports_to": "Director Platform Engineering",
        "seniority": "Senior IC",
        "work_location": "Berlin HQ",
    },
    "tasks": {
        "core": [
            "Design resilience reviews with platform squads",
            "Automate incident response playbooks for robotics fleets",
            "Partner with hardware teams to model failure scenarios",
        ],
        "secondary": [
            "Mentor engineers on observability best practices",
            "Evaluate tooling for chaos engineering and reliability",
        ],
        "success_metrics": [
            "Mean time to recovery under 20 minutes",
            "Quarterly reliability scorecard adoption across sites",
        ],
    },
    "skills": {
        "must_have": ["Python", "Kubernetes", "Site Reliability Engineering"],
        "nice_to_have": ["PLC expertise", "Robotics integration"],
        "certifications": ["AWS Solutions Architect Professional"],
        "tools": ["Prometheus", "Grafana", "Terraform"],
        "languages": ["English B2+"],
    },
    "benefits": {
        "salary_range": "€85k–€105k",
        "currency": "EUR",
        "bonus": "10% annual bonus based on platform uptime",
        "equity": "VSOP available after probation",
        "perks": ["Learning budget", "Hardware allowance"],
        "wellbeing": ["Mental health days", "Onsite gym membership"],
        "relocation_support": "Full visa & relocation package for EU moves",
        "on_call": OnCallRequirement.ROTATION.value,
    },
    "interview_process": {
        "steps": [
            "Recruiter screen",
            "Technical deep dive",
            "System design workshop",
            "Executive conversation",
        ],
        "interviewers": ["Talent Partner", "Staff Reliability Engineer", "VP Engineering"],
        "evaluation_criteria": [
            "Incident leadership",
            "Automation-first mindset",
            "Cross-functional influence",
        ],
        "decision_timeline": "Approx. 3 weeks",
        "notes": "Panel offers remote interviews across CET and EST time zones.",
    },
    "summary": {
        "headline": "Build resilient robotics platforms for sustainable manufacturing.",
        "value_proposition": "Join a low-ego platform team scaling predictive robotics while keeping uptime high.",
        "culture_highlights": [
            "Inclusive, multilingual engineering culture",
            "Tight collaboration with hardware and AI research",
        ],
        "next_steps": ["Share portfolio link", "Confirm salary expectations"],
    },
    "sources": {
        "company.name": {
            "source": SourceType.EXTRACT.value,
            "confidence": 0.9,
            "source_url": "https://acmerobotics.example/jobs/reliability",
        },
        "role.title": {"source": SourceType.USER.value, "confidence": 1.0},
        "benefits.salary_range": {
            "source": SourceType.WEB.value,
            "confidence": 0.75,
            "source_url": "https://salary-insights.example/acme-robotics",
        },
    },
    "missing_fields": {
        "interview_process.notes": {
            "required": False,
            "reason": "Panel agenda pending final review",
        },
        "benefits.relocation_support": {
            "required": True,
            "reason": "HR Ops to confirm allowance tier",
            "owner": "HR Operations",
        },
    },
}


def default_recruiting_wizard() -> RecruitingWizard:
    """Return the default wizard payload used for smoke tests and roundtrips."""

    payload = RecruitingWizard.model_validate(_DEFAULT_WIZARD_DATA)
    if KEYS_CANONICAL:  # defensive: ensure the schema stayed aligned.
        missing = sorted(
            key
            for key in payload.sources.root
            if key not in KEYS_CANONICAL  # type: ignore[attr-defined]
        )
        if missing:
            raise ValueError(f"Source map not aligned with canonical keys: {missing}")
    return payload


__all__ = ["default_recruiting_wizard"]
