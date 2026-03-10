from generators.interview_guide import _prepare_interview_payload
from generators.job_ad import _prepare_job_ad_payload


def _sample_payload() -> dict:
    return {
        "position": {
            "occupation_label": "Software developer",
            "occupation_uri": "http://data.europa.eu/esco/occupation/123",
            "occupation_group": "software developers",
        },
        "requirements": {
            "hard_skills_required": ["Python"],
            "skill_mappings": {
                "hard_skills_required": [
                    {
                        "name": "Python",
                        "normalized_name": "Python",
                        "esco_uri": "http://data.europa.eu/esco/skill/python",
                        "skill_type": "http://data.europa.eu/esco/skill-type/skill",
                        "weight": None,
                    }
                ],
                "hard_skills_optional": [],
                "soft_skills_required": [],
                "soft_skills_optional": [],
                "tools_and_technologies": [],
            },
        },
    }


def test_job_ad_payload_contains_esco_references() -> None:
    payload = _prepare_job_ad_payload(_sample_payload())
    refs = payload.get("meta", {}).get("esco_references", {})
    assert refs.get("occupation", {}).get("uri")
    assert refs.get("skill_mappings", {}).get("hard_skills_required")


def test_interview_payload_contains_esco_references() -> None:
    payload = _prepare_interview_payload(_sample_payload())
    refs = payload.get("meta", {}).get("esco_references", {})
    assert refs.get("occupation", {}).get("label") == "Software developer"
