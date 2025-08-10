"""CLI for running the extraction pipeline locally."""

from __future__ import annotations

import argparse
import os
from pathlib import Path


def main() -> None:
    """Parse arguments and print validated JSON to stdout.

    The command reads a local job description file, extracts text, and runs the
    LLM pipeline without requiring Streamlit. Example::

        python -m cli.extract --file jd.pdf --title "..." --url "..." --mode json
    """

    parser = argparse.ArgumentParser(description="Vacalyser JSON extractor")
    parser.add_argument(
        "--file", required=True, help="Path to the job description file"
    )
    parser.add_argument("--title", help="Optional job title for context")
    parser.add_argument("--url", help="Optional source URL for context")
    parser.add_argument(
        "--mode",
        choices=["plain", "json", "function"],
        default=os.getenv("LLM_MODE", "plain"),
        help="LLM mode: plain, json, or function",
    )
    args = parser.parse_args()

    # Ensure mode is respected by the client module
    os.environ["LLM_MODE"] = args.mode

    from utils import extract_text_from_file
    from llm.client import extract_and_parse

    file_path = Path(args.file)
    if not file_path.exists():
        raise SystemExit(f"File not found: {file_path}")

    text = extract_text_from_file(file_path.read_bytes(), file_path.name)
    if not text:
        raise SystemExit("No text could be extracted from the file.")

    jd = extract_and_parse(text, title=args.title, url=args.url)
    print(jd.model_dump_json(indent=2))


if __name__ == "__main__":  # pragma: no cover
    main()
