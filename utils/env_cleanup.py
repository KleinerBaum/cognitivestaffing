"""Helpers for stripping API mode overrides from environment files."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

DEFAULT_FLAG_KEYS: tuple[str, ...] = (
    "USE_RESPONSES_API",
    "USE_CLASSIC_API",
    "RESPONSES_ALLOW_TOOLS",
    "OPENAI_MODEL",
    "DEFAULT_MODEL",
    "LIGHTWEIGHT_MODEL",
    "MEDIUM_REASONING_MODEL",
    "REASONING_MODEL",
    "OPENAI_BASE_URL",
    "OPENAI_API_BASE_URL",
)


def _extract_key(line: str) -> str | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None

    if stripped.startswith("export "):
        stripped = stripped[len("export ") :].strip()

    if "=" not in stripped:
        return None

    return stripped.split("=", 1)[0].strip()


def scrub_env_file(path: Path, *, keys: Sequence[str] | None = None) -> tuple[int, int]:
    """Remove provided keys from a ``.env``-style file.

    Args:
        path: Path to the env file.
        keys: Optional sequence of keys to remove. ``DEFAULT_FLAG_KEYS`` is used
            when omitted.

    Returns:
        A tuple of ``(removed, remaining)`` line counts. ``remaining`` reflects
        the total lines written back to disk (including comments and blanks).
    """

    target_keys = set(keys or DEFAULT_FLAG_KEYS)
    raw_text = path.read_text()
    content = raw_text.splitlines()
    if raw_text.endswith("\n"):
        content.append("")
    kept: list[str] = []
    removed_count = 0

    for line in content:
        key = _extract_key(line)
        if key and key in target_keys:
            removed_count += 1
            continue
        kept.append(line)

    path.write_text("\n".join(kept) + ("\n" if kept else ""))
    return removed_count, len(kept)
