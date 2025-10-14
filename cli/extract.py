"""CLI for running the extraction pipeline locally."""

from __future__ import annotations

import argparse
from pathlib import Path
import json


def main() -> None:
    """Parse arguments and print validated JSON to stdout.

    The command reads a local job posting file (PDF, DOCX or text), extracts
    text using the same logic as the Streamlit app – including optional OCR for
    scanned PDFs – and runs the LLM pipeline without requiring Streamlit.
    Example::

        python -m cli.extract --file profile.pdf --title "..." --url "..."
    """

    parser = argparse.ArgumentParser(description="Cognitive Needs JSON extractor")
    parser.add_argument("--file", required=True, help="Path to the job posting file")
    parser.add_argument("--title", help="Optional job title for context")
    parser.add_argument("--url", help="Optional source URL for context")
    args = parser.parse_args()

    from ingest.extractors import extract_text_from_file
    from ingest.reader import clean_structured_document
    from config_loader import load_json
    from openai_utils import extract_with_function
    from config import ModelTask, VECTOR_STORE_ID, get_model_for
    from llm.rag_pipeline import (
        build_field_queries,
        build_global_context,
        collect_field_contexts,
    )

    file_path = Path(args.file)
    if not file_path.exists():
        raise SystemExit(f"File not found: {file_path}")

    with file_path.open("rb") as fh:
        try:
            structured = clean_structured_document(extract_text_from_file(fh))
            text = structured.text
        except ValueError as e:
            raise SystemExit(str(e))
    if not text:
        raise SystemExit("No text could be extracted from the file.")

    schema = load_json("schema/need_analysis.schema.json", fallback={})
    specs = build_field_queries(schema)
    contexts = collect_field_contexts(
        specs,
        base_text=text,
        vector_store_id=VECTOR_STORE_ID,
    )
    global_chunks = build_global_context(text)
    result = extract_with_function(
        text,
        schema,
        model=get_model_for(ModelTask.EXTRACTION),
        field_contexts=contexts,
        global_context=global_chunks,
    )
    print(json.dumps(result.data, indent=2))


if __name__ == "__main__":  # pragma: no cover
    main()
