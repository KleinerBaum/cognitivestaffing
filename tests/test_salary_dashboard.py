from components.salary_dashboard import compute_expected_salary


def test_compute_salary_permanent() -> None:
    salary, mode = compute_expected_salary(
        ["Python", "SQL"], ["Docker"], "Senior", "Berlin", "permanent"
    )
    assert mode == "annual"
    assert salary == 71500


def test_compute_salary_contract() -> None:
    rate, mode = compute_expected_salary(["Python"], [], "Mid", "Remote", "contract")
    assert mode == "hourly"
    assert rate == 37.8
