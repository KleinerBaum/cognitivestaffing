import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from models.need_analysis import NeedAnalysisProfile, Process, Stakeholder, Phase


def test_process_model_supports_stakeholders_and_phases():
    process = Process(
        interview_stages=2,
        stakeholders=[
            Stakeholder(
                name="Alice",
                role="Recruiter",
                email="alice@example.com",
                primary=True,
                information_loop_phases=[0, 1],
            ),
            Stakeholder(name="Bob", role="Manager", email="bob@example.com"),
            Stakeholder(name="Carol", role="HR"),
            Stakeholder(name="Dana", role="Coordinator", email=""),
        ],
        phases=[
            Phase(
                name="Phone Screen",
                interview_format="phone",
                participants=["Alice"],
                docs_required="",
                assessment_tests=False,
                timeframe="Week 1",
            ),
            Phase(
                name="On-site",
                interview_format="on_site",
                participants=["Bob"],
                docs_required="Portfolio",
                assessment_tests=True,
                timeframe="Week 2",
            ),
        ],
        recruitment_timeline="6 weeks",
        process_notes="Notes",
        application_instructions="Send one PDF",
        onboarding_process="Buddy program",
    )
    profile = NeedAnalysisProfile(process=process)
    assert profile.process.interview_stages == 2
    assert profile.process.stakeholders[0].primary is True
    assert profile.process.stakeholders[0].information_loop_phases == [0, 1]
    assert profile.process.stakeholders[2].email is None
    assert profile.process.stakeholders[3].email is None
    assert profile.process.phases[1].participants == ["Bob"]


def test_stakeholder_blank_email_coerced_to_none():
    stakeholder = Stakeholder(name="Eve", role="HR", email="   ")
    assert stakeholder.email is None
    assert stakeholder.model_dump()["email"] is None
