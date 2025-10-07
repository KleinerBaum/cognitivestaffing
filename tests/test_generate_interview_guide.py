from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import openai_utils


def test_generate_interview_guide_includes_culture_question():
    output = openai_utils.generate_interview_guide(
        "Engineer",
        responsibilities="Design systems\nWrite code",
        hard_skills=["Python", "SQL"],
        soft_skills=["Teamwork"],
        company_culture="Collaborative and transparent",
        tone="casual and friendly",
        num_questions=5,
        lang="en",
    )

    assert "Interview Guide – Engineer" in output
    assert "**Company culture:** Collaborative and transparent" in output
    assert "### 2. Which aspects of the culture we described" in output
    assert "casual and friendly" in output


def test_generate_interview_guide_de_language():
    output = openai_utils.generate_interview_guide(
        "Ingenieur:in",
        responsibilities="Systeme entwerfen",
        hard_skills=["Python"],
        lang="de",
        num_questions=3,
        tone="strukturierter Ton",
        company_culture="Transparente Zusammenarbeit",
    )

    assert "Interviewleitfaden – Ingenieur:in" in output
    assert "**Zielgruppe:**" in output
    assert "Transparente Zusammenarbeit" in output
    assert "## Fragen & Bewertungsleitfaden" in output


def test_generate_interview_guide_uses_responsibilities_and_skills():
    output = openai_utils.generate_interview_guide(
        "Engineer",
        responsibilities="Design systems\nWrite code",
        hard_skills=["Python"],
        soft_skills=["Teamwork"],
        num_questions=4,
    )

    assert "Design systems" in output
    assert "Write code" in output
    assert "Python" in output
    assert "Teamwork" in output


def test_generate_interview_guide_respects_question_limit():
    output = openai_utils.generate_interview_guide(
        "Engineer",
        responsibilities="One\nTwo\nThree",
        hard_skills=["Python", "SQL"],
        soft_skills=["Teamwork", "Empathy"],
        num_questions=3,
    )

    question_count = output.count("### ")
    assert question_count == 3
