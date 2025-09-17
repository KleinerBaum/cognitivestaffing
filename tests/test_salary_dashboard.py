from components.salary_dashboard import compute_expected_salary


def test_compute_salary_permanent() -> None:
    salary, mode = compute_expected_salary(
        ["Python", "SQL"],
        ["Docker"],
        "Senior",
        "Berlin",
        "permanent",
        "Data Scientist",
        [
            "Develop predictive models",
            "Collaborate with stakeholders",
            "Deploy ML services",
        ],
        ["English"],
        "Technology",
    )
    assert mode == "annual"
    assert salary == 128068


def test_compute_salary_contract() -> None:
    rate, mode = compute_expected_salary(
        ["Python"],
        [],
        "Mid",
        "Remote",
        "contract",
        "Data Engineer",
        ["Maintain data pipelines", "Support business stakeholders"],
        ["English", "German"],
        "Consulting",
    )
    assert mode == "hourly"
    assert rate == 49.93


def test_additional_languages_raise_salary() -> None:
    base_salary, _ = compute_expected_salary(
        ["Python"],
        ["Docker"],
        "Mid",
        "Berlin",
        "permanent",
        "Software Engineer",
        ["Ship features", "Maintain codebase"],
        ["English"],
        "Technology",
    )
    multi_language_salary, _ = compute_expected_salary(
        ["Python"],
        ["Docker"],
        "Mid",
        "Berlin",
        "permanent",
        "Software Engineer",
        ["Ship features", "Maintain codebase"],
        ["English", "German"],
        "Technology",
    )
    assert multi_language_salary > base_salary


def test_industry_impacts_salary() -> None:
    tech_salary, _ = compute_expected_salary(
        ["Python"],
        [],
        "Mid",
        "Berlin",
        "permanent",
        "Software Engineer",
        ["Ship features"],
        ["English"],
        "Technology",
    )
    nonprofit_salary, _ = compute_expected_salary(
        ["Python"],
        [],
        "Mid",
        "Berlin",
        "permanent",
        "Software Engineer",
        ["Ship features"],
        ["English"],
        "Nonprofit",
    )
    assert tech_salary > nonprofit_salary
