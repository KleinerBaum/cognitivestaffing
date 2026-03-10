from utils.skill_taxonomy import build_skill_mappings, map_skill, normalize_skill_label


def test_normalize_skill_label_synonyms():
    assert normalize_skill_label("excel") == "Microsoft Excel"
    assert normalize_skill_label("proj. management") == "Project management"


def test_map_skill_esco_uri_lookup(monkeypatch):
    monkeypatch.setattr(
        "utils.skill_taxonomy.lookup_esco_skill",
        lambda *_args, **_kwargs: {
            "preferredLabel": "Microsoft Excel",
            "uri": "http://data.europa.eu/esco/skill/excel",
            "skillType": "http://data.europa.eu/esco/skill-type/skill",
        },
    )
    entry = map_skill("Excel")
    assert entry is not None
    assert entry["normalized_name"] == "Microsoft Excel"
    assert entry["esco_uri"] is not None
    assert entry["skill_type"] is not None


def test_build_skill_mappings_populates_required_and_soft_skills(monkeypatch):
    monkeypatch.setattr(
        "utils.skill_taxonomy.lookup_esco_skill",
        lambda term, **_kwargs: {"preferredLabel": term, "uri": f"uri://{term}", "skillType": "type://skill"},
    )
    requirements = {
        "hard_skills_required": ["Python", "proj. management"],
        "soft_skills_required": ["communication"],
        "tools_and_technologies": ["git"],
    }
    mappings = build_skill_mappings(requirements)

    python_entry = mappings["hard_skills_required"][0]
    assert python_entry["normalized_name"] == "Python"
    assert python_entry["esco_uri"] is not None
    assert python_entry["skill_type"] == "type://skill"

    project_entry = mappings["hard_skills_required"][1]
    assert project_entry["normalized_name"] == "Project management"

    assert mappings["soft_skills_required"][0]["normalized_name"] == "Communication"
    assert mappings["tools_and_technologies"][0]["normalized_name"] == "Git"


def test_programming_language_falls_back_to_general_esco_uri(monkeypatch):
    monkeypatch.setattr("utils.skill_taxonomy.lookup_esco_skill", lambda *_args, **_kwargs: {})
    entry = map_skill("Rust")
    assert entry is not None
    assert entry["esco_uri"] is not None
    assert "942d4e8d" in entry["esco_uri"]
