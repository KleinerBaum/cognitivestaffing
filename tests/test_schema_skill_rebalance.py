from core.schema import canonicalize_profile_payload


def test_canonicalize_profile_payload_rebalances_german_skill_lists():
    payload = {
        "requirements": {
            "hard_skills_required": [
                "Analytisches Denken",
                "Teamfähigkeit",
                "Python-Kenntnisse",
                "Englisch (C1)",
                "Deutsch (B2)",
            ],
            "soft_skills_optional": ["Kundenorientierung"],
            "tools_and_technologies": ["Excel"],
        }
    }

    normalized = canonicalize_profile_payload(payload)
    requirements = normalized.get("requirements", {})

    assert "Analytisches Denken" in requirements["hard_skills_required"]
    assert "Teamfähigkeit" in requirements["soft_skills_required"]
    assert "Python-Kenntnisse" in requirements["tools_and_technologies"]
    assert "Excel" in requirements["tools_and_technologies"]
    assert "Englisch (C1)" in requirements["languages_required"]
    assert "Deutsch (B2)" in requirements["languages_required"]
    assert "Kundenorientierung" in requirements["soft_skills_optional"]
