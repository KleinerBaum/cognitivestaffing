from utils.skill_taxonomy import build_skill_mappings, map_skill, normalize_skill_label


def test_normalize_skill_label_synonyms():
    assert normalize_skill_label("excel") == "Microsoft Excel"
    assert normalize_skill_label("proj. management") == "Project management"


def test_map_skill_esco_uri_lookup():
    entry = map_skill("Excel")
    assert entry is not None
    assert entry["normalized_name"] == "Microsoft Excel"
    assert entry["esco_uri"] is not None


def test_build_skill_mappings_populates_required_and_soft_skills():
    requirements = {
        "hard_skills_required": ["Python", "proj. management"],
        "soft_skills_required": ["communication"],
        "tools_and_technologies": ["git"],
    }
    mappings = build_skill_mappings(requirements)

    python_entry = mappings["hard_skills_required"][0]
    assert python_entry["normalized_name"] == "Python"
    assert python_entry["esco_uri"] is not None

    project_entry = mappings["hard_skills_required"][1]
    assert project_entry["normalized_name"] == "Project management"

    assert mappings["soft_skills_required"][0]["normalized_name"] == "Communication"
    assert mappings["tools_and_technologies"][0]["normalized_name"] == "Git"


def test_programming_language_falls_back_to_general_esco_uri():
    entry = map_skill("Rust")
    assert entry is not None
    assert entry["esco_uri"] is not None
    assert "942d4e8d" in entry["esco_uri"]
