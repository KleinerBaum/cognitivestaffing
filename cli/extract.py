"""CLI for running the extraction pipeline locally."""

from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    """Parse arguments and print validated JSON to stdout.

    The command reads a local job description file (PDF, DOCX or text), extracts
    text using the same logic as the Streamlit app – including optional OCR for
    scanned PDFs – and runs the LLM pipeline without requiring Streamlit.
    Example::

        python -m cli.extract --file jd.pdf --title "..." --url "..."
    """

    parser = argparse.ArgumentParser(description="Vacalyser JSON extractor")
    parser.add_argument(
        "--file", required=True, help="Path to the job description file"
    )
    parser.add_argument("--title", help="Optional job title for context")
    parser.add_argument("--url", help="Optional source URL for context")
    args = parser.parse_args()

    from ingest.extractors import extract_text_from_file
    from llm.client import extract_and_parse

    file_path = Path(args.file)
    if not file_path.exists():
        raise SystemExit(f"File not found: {file_path}")

    with file_path.open("rb") as fh:
        try:
            text = extract_text_from_file(fh)
        except ValueError as e:
            raise SystemExit(str(e))
    if not text:
        raise SystemExit("No text could be extracted from the file.")

    jd = extract_and_parse(text, title=args.title, url=args.url)
    print(jd.model_dump_json(indent=2))


if __name__ == "__main__":  # pragma: no cover
    main()
