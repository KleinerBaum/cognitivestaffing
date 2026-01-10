"""CLI helper to clear API mode and model overrides from env files."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from utils.env_cleanup import DEFAULT_FLAG_KEYS, scrub_env_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Remove API mode overrides (USE_CLASSIC_API/USE_RESPONSES_API) and "
            "model tier overrides from a .env-style file."
        )
    )
    parser.add_argument(
        "env_file",
        type=Path,
        nargs="?",
        default=Path(".env"),
        help="Path to the .env-style file to clean (defaults to ./ .env).",
    )
    parser.add_argument(
        "--extra-key",
        "-k",
        action="append",
        dest="extra_keys",
        default=None,
        help="Additional environment keys to strip alongside the defaults.",
    )
    return parser.parse_args()


def collect_keys(extra_keys: Sequence[str] | None) -> tuple[str, ...]:
    if not extra_keys:
        return DEFAULT_FLAG_KEYS
    unique_keys = list(DEFAULT_FLAG_KEYS) + [key.strip() for key in extra_keys if key.strip()]
    return tuple(dict.fromkeys(unique_keys))


def main() -> None:
    args = parse_args()
    env_file: Path = args.env_file
    keys = collect_keys(args.extra_keys)

    if not env_file.exists():
        print(f"No env file found at {env_file}; nothing to clean.")
        return

    removed, remaining = scrub_env_file(env_file, keys=keys)
    removed_keys = ", ".join(keys)
    print(f"Removed {removed} override lines from {env_file} (kept {remaining}).\nCleared keys: {removed_keys}")


if __name__ == "__main__":
    main()
