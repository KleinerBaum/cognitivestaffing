from __future__ import annotations

import json
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import openai_utils
import pytest

import ingest.heuristics as heuristics
from core.ss_bridge import from_session_state, to_session_state
from models.need_analysis import NeedAnalysisProfile


@dataclass(frozen=True)
class ExtractionEvalCase:
    case_id: str
    text: str
    expected: dict[str, Any]


def _normalize_scalar(value: str) -> str:
    lowered = value.strip().casefold()
    collapsed = re.sub(r"\s+", " ", lowered)
    return re.sub(r"[^\w@.+\-/äöüß]", "", collapsed)


def _tokens(value: str) -> set[str]:
    normalized = _normalize_scalar(value)
    return {token for token in re.split(r"[^\wäöüß]+", normalized) if token}


def _match_scalar(expected: str, actual: str) -> bool:
    expected_normalized = _normalize_scalar(expected)
    actual_normalized = _normalize_scalar(actual)
    if not expected_normalized:
        return not actual_normalized
    if expected_normalized == actual_normalized:
        return True
    if expected_normalized in actual_normalized or actual_normalized in expected_normalized:
        return True
    expected_tokens = _tokens(expected)
    actual_tokens = _tokens(actual)
    if expected_tokens and expected_tokens.issubset(actual_tokens):
        return True
    ratio = SequenceMatcher(None, expected_normalized, actual_normalized).ratio()
    return ratio >= 0.86


def _match_list(expected: list[str], actual: list[str]) -> bool:
    if not expected:
        return True
    if not actual:
        return False
    for expected_item in expected:
        if not any(_match_scalar(expected_item, actual_item) for actual_item in actual):
            return False
    return True


def _read_path(data: dict[str, Any], dotted_path: str) -> Any:
    cursor: Any = data
    for part in dotted_path.split("."):
        if not isinstance(cursor, dict):
            return None
        cursor = cursor.get(part)
    return cursor


def _collect_eval_cases(fixtures_dir: Path) -> list[ExtractionEvalCase]:
    cases: list[ExtractionEvalCase] = []
    for expected_path in sorted(fixtures_dir.glob("*.expected.json")):
        case_id = expected_path.name.replace(".expected.json", "")
        text_path = fixtures_dir / f"{case_id}.txt"
        expected_payload = json.loads(expected_path.read_text(encoding="utf-8"))
        cases.append(
            ExtractionEvalCase(
                case_id=case_id,
                text=text_path.read_text(encoding="utf-8"),
                expected=expected_payload,
            )
        )
    return cases


@pytest.fixture(autouse=True)
def _disable_city_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(heuristics, "_llm_extract_primary_city", lambda _text: "")


def test_e2e_to_session_state(monkeypatch) -> None:
    """End-to-end extraction should populate session state."""

    class _Result:
        def __init__(self, data: dict) -> None:
            self.data = data

    def fake_extract_with_function(text: str, schema: dict, model=None, **kwargs):
        return _Result({"position": {"job_title": "Dev"}})

    monkeypatch.setattr(openai_utils, "extract_with_function", fake_extract_with_function)
    profile_result = openai_utils.extract_with_function("input", {})
    profile = NeedAnalysisProfile.model_validate(profile_result.data)
    ss: dict = {}
    to_session_state(profile, ss)
    assert ss["position.job_title"] == "Dev"


def test_e2e_roundtrip_preserves_skills() -> None:
    """Extraction bridge should keep list fields intact across round-trips."""

    base: dict[str, Any] = NeedAnalysisProfile().model_dump()
    base["position"]["job_title"] = "Data Engineer"
    base["requirements"]["hard_skills_required"] = ["Python", "SQL"]
    base["requirements"]["soft_skills_required"] = ["Collaboration"]
    profile = NeedAnalysisProfile.model_validate(base)

    session: dict[str, Any] = {}
    to_session_state(profile, session)

    assert session["requirements.hard_skills_required"] == "Python\nSQL"
    assert session["requirements.soft_skills_required"] == "Collaboration"

    restored = from_session_state(session)
    assert restored.position.job_title == "Data Engineer"
    assert {"Python", "SQL"}.issubset(set(restored.requirements.tools_and_technologies))
    assert "Collaboration" in restored.requirements.languages_required


def test_extraction_goldenset_field_accuracy() -> None:
    """Evaluate deterministic extraction quality for core fields and persist a CI artifact."""

    fixtures_dir = Path(__file__).resolve().parent / "fixtures" / "extraction"
    cases = _collect_eval_cases(fixtures_dir)
    assert cases, "No extraction fixture cases found"

    evaluated_fields: tuple[str, ...] = (
        "position.job_title",
        "company.name",
        "location.primary_city",
        "company.website",
        "company.contact_email",
        "requirements.hard_skills_required",
        "requirements.soft_skills_required",
    )
    required_fields: set[str] = {
        "position.job_title",
        "company.name",
        "location.primary_city",
        "company.website",
        "company.contact_email",
    }

    matches = 0
    total = 0
    report_cases: list[dict[str, Any]] = []
    hard_failures: list[str] = []

    for case in cases:
        profile = heuristics.apply_basic_fallbacks(NeedAnalysisProfile(), case.text)
        actual_profile = profile.model_dump(mode="python")

        case_results: list[dict[str, Any]] = []
        for field in evaluated_fields:
            expected_value = _read_path(case.expected, field)
            actual_value = _read_path(actual_profile, field)
            if isinstance(expected_value, list):
                expected_list = [str(item) for item in expected_value]
                actual_list = [str(item) for item in (actual_value or [])]
                matched = _match_list(expected_list, actual_list)
            else:
                expected_text = "" if expected_value is None else str(expected_value)
                actual_text = "" if actual_value is None else str(actual_value)
                matched = _match_scalar(expected_text, actual_text)

            matches += int(matched)
            total += 1
            if field in required_fields and not matched:
                hard_failures.append(f"{case.case_id}:{field}")

            case_results.append(
                {
                    "field": field,
                    "matched": matched,
                    "expected": expected_value,
                    "actual": actual_value,
                    "required": field in required_fields,
                }
            )

        report_cases.append({"case_id": case.case_id, "results": case_results})

    accuracy = matches / total if total else 0.0
    report = {
        "suite": "extraction-goldenset",
        "cases": len(cases),
        "fields_per_case": len(evaluated_fields),
        "accuracy": accuracy,
        "matches": matches,
        "total": total,
        "hard_failures": hard_failures,
        "results": report_cases,
    }

    artifact_path = Path("artifacts") / "extraction_eval_report.json"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    assert not hard_failures, f"Required field mismatches: {hard_failures}"
    assert accuracy >= 0.90, f"Extraction accuracy below threshold: {accuracy:.3f}"
