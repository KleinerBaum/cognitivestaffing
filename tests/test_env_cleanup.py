from __future__ import annotations

from pathlib import Path

import pytest

from utils.env_cleanup import DEFAULT_FLAG_KEYS, scrub_env_file


@pytest.fixture()
def tmp_env_file(tmp_path: Path) -> Path:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "# comment should stay",
                "USE_CLASSIC_API=1",
                "export USE_RESPONSES_API=0",
                "OPENAI_MODEL=gpt-4o-mini",
                "SAFE_KEY=keep-me",
                "LIGHTWEIGHT_MODEL=gpt-4o-mini",
                "",
            ]
        )
    )
    return env_file


def test_scrub_env_file_removes_defaults(tmp_env_file: Path) -> None:
    removed, remaining = scrub_env_file(tmp_env_file)

    assert removed == 4
    assert remaining == 3
    assert "USE_CLASSIC_API" not in tmp_env_file.read_text()
    assert "SAFE_KEY=keep-me\n" in tmp_env_file.read_text()


def test_scrub_env_file_with_extra_keys(tmp_env_file: Path) -> None:
    extra_key = "SAFE_KEY"
    removed, _ = scrub_env_file(tmp_env_file, keys=DEFAULT_FLAG_KEYS + (extra_key,))

    assert removed == 5
    assert "SAFE_KEY" not in tmp_env_file.read_text()
