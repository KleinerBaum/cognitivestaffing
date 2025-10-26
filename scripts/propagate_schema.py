#!/usr/bin/env python3
"""Synchronise RecruitingWizard schema artifacts (CS_SCHEMA_PROPAGATE / PIPE_PROP)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.propagate import run_propagation, write_report


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check or regenerate RecruitingWizard schema artifacts.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write generated files to disk when drift is detected.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=PROJECT_ROOT,
        help="Repository root (defaults to the project root).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    mode = "apply" if args.apply else "check"
    result = run_propagation(args.root, apply=args.apply, mode=mode)
    report_path = write_report(args.root, result.report)

    if result.has_drift:
        message = f"Schema drift detected. See {report_path}."
        if args.apply:
            print(f"Updated generated files. {message}")
            return 0
        print(message)
        return 1

    print(f"Schema artifacts are up to date. Report available at {report_path}.")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    sys.exit(main())
