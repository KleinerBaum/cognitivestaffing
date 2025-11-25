from utils.json_repair import JsonRepairStatus, parse_json_with_repair


def test_parse_json_ok() -> None:
    raw = '{"title": "Engineer"}'
    result = parse_json_with_repair(raw)

    assert result.status is JsonRepairStatus.OK
    assert result.payload == {"title": "Engineer"}
    assert not result.low_confidence


def test_parse_json_trailing_comma() -> None:
    raw = '{"title": "Engineer",}'

    result = parse_json_with_repair(raw)

    assert result.status is JsonRepairStatus.REPAIRED
    assert result.payload == {"title": "Engineer"}
    assert result.low_confidence
    assert result.issues


def test_parse_json_unbalanced_braces() -> None:
    raw = '{"role": {"name": "Developer"}'

    result = parse_json_with_repair(raw)

    assert result.status is JsonRepairStatus.REPAIRED
    assert result.payload == {"role": {"name": "Developer"}}


def test_parse_json_failure() -> None:
    result = parse_json_with_repair("not-json")

    assert result.status is JsonRepairStatus.FAILED
    assert result.payload is None
    assert result.issues
