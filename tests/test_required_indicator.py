from wizard import REQUIRED_PREFIX, REQUIRED_SUFFIX


def test_required_indicator_format() -> None:
    assert REQUIRED_SUFFIX.endswith(":red[*]")
    assert REQUIRED_PREFIX.startswith(":red[*]")
