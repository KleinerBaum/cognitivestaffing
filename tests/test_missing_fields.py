from __future__ import annotations

from dataclasses import dataclass

from wizard.missing_fields import get_path_value, is_blank, missing_fields


@dataclass
class Company:
    name: str
    meta: dict[str, int]


@dataclass
class Profile:
    company: Company


def test_get_path_value_with_dict() -> None:
    profile = {"company": {"name": "Acme", "meta": {"size": 12}}}

    assert get_path_value(profile, "company.name") == "Acme"
    assert get_path_value(profile, "company.meta.size") == 12
    assert get_path_value(profile, "company.missing") is None


def test_get_path_value_with_objects() -> None:
    profile = Profile(company=Company(name="Nimbus", meta={"size": 4}))

    assert get_path_value(profile, "company.name") == "Nimbus"
    assert get_path_value(profile, "company.meta.size") == 4
    assert get_path_value(profile, "company.missing") is None


def test_is_blank_values() -> None:
    assert is_blank(None) is True
    assert is_blank("") is True
    assert is_blank("  ") is True
    assert is_blank([]) is True
    assert is_blank({}) is True
    assert is_blank(set()) is True
    assert is_blank(0) is False
    assert is_blank(False) is False
    assert is_blank("ready") is False


def test_missing_fields_detects_blank_paths() -> None:
    profile = {
        "company": {"name": "Acme", "site": " "},
        "location": {},
    }
    paths = [
        "company.name",
        "company.site",
        "location.city",
        "missing.path",
    ]

    assert missing_fields(profile, paths) == [
        "company.site",
        "location.city",
        "missing.path",
    ]
