# LLM Integration Review: Job-Ad Extraction Pipeline

This document describes the end-to-end flow for extracting structured vacancy profiles from job advertisements, and highlights the LLM touch points that require special attention when integrating new functionality or debugging failures.

## 1. Ingestion

1. **Entry points**
   - File uploads (`PDF`, `DOCX`, `TXT`) and URLs converge in `ingest.extractors.extract_text_from_file()` and `ingest.extractors.extract_text_from_url()`.
   - Raw bytes are normalised before downstream processing. PDFs and DOCX documents use format-specific `_extract_*` helpers, while text files rely on charset detection for decoding.
2. **Output**
   - A `StructuredDocument` containing ordered blocks (`heading`, `paragraph`, `table`, or generic `text`).

## 2. Cleaning

`ingest.reader.clean_structured_document()` removes boilerplate, PII, and navigation noise.

- The function first calls `clean_job_text()` on the flat document text.
- It filters navigation/footer artefacts via `_looks_like_navigation()` and drops empty blocks.
- Depending on the resulting structure, it either rebuilds a cleaned `StructuredDocument` or returns a flattened text representation.

## 3. Field Context Collection

1. **Schema**
   - `schemas/need_analysis.schema.json` defines the vacancy fields, enforced by `NeedAnalysisProfile` in `schemas.py`.
2. **Query planning**
   - `llm.rag_pipeline.build_field_queries()` creates prompts per field.
3. **Retrieval**
   - `llm.rag_pipeline.collect_field_contexts()` fetches relevant `RetrievedChunk` instances from the configured vector store (`VECTOR_STORE_ID`). Each chunk is paired with the originating field query.
4. **Optional global context**
   - `build_global_context()` aggregates the top-k snippets to provide holistic document background when the extraction prompt needs additional grounding.

## 4. Structured Extraction Call

`openai_utils.extraction.extract_with_function()` orchestrates the actual LLM call.

- **System prompt**: Loaded from `llm.extraction.context.system` (with a default fallback) to describe the extraction task and schema expectations.
- **User payload**: Either the cleaned document text or a JSON payload that maps each field to its retrieved context (when RAG is active).
- **OpenAI invocation**: `api.call_chat_api()` is called with deterministic settings (`temperature=0.0`).
  - The tool definition comes from `build_extraction_tool("NeedAnalysisProfile", ...)`, forcing the assistant to reply via a function call that matches the schema.
  - If the model returns a normal message instead of a tool call, the function retries with a JSON-mode style prompt that instructs the model to emit schema-conforming JSON.
- **Validation**: `_extract_tool_arguments()` extracts the raw JSON. The payload is parsed and validated via `NeedAnalysisProfile` (Pydantic), ensuring strong typing before the profile enters the wizard state.

## 5. Normalisation & Repair

1. **Canonicalisation**
   - `core.schema.coerce_and_fill()` applies `ALIASES`, filters unknown keys, and coerces scalar types before validation.
2. **LLM repair fallback**
   - When validation fails, the helper calls the OpenAI Responses API JSON repair routine (`repair_profile_payload`) with the validation errors.
   - Repaired payloads are canonicalised again and revalidated to ensure schema compliance.
3. **Post-validation cleanup**
   - `utils.normalization.normalize_profile()` strips noise (whitespace, duplicate list entries, inconsistent casing), harmonises countries/languages, and validates the cleaned dictionary.
   - If cleanup introduces schema issues, the helper invokes JSON repair once more before falling back to the last valid snapshot.
   - Normalised payloads flow back into `NeedAnalysisProfile` instances to guarantee type safety before reaching Streamlit state.

## 6. Error Handling & Retries

- All LLM invocations return a `ChatCallResult` wrapper (`ok`, `usage`, `error`, `raw`). Downstream UI components translate errors into localized feedback and expose retry actions with exponential backoff.
- When RAG is disabled (`VECTOR_STORE_ID` missing), the pipeline gracefully falls back to text-only extraction without surfacing retrieval errors to the user.

## 6. Integration Checklist

When modifying or extending the extraction pipeline:

1. **Schema propagation**: Update the JSON schema, `NeedAnalysisProfile`, UI components, exports, and tests together.
2. **Cost and latency controls**: Keep prompts concise, prefer `gpt-5.1-mini` where acceptable, and scope vector retrieval to relevant fields.
3. **Validation**: Maintain strict Pydantic validation; never accept free-form text for structured fields.
4. **Localization**: Extend both English and German resources when adding user-facing copy.
5. **Testing**: Run `ruff format`, `ruff check`, `mypy`, and `pytest` locally; update or add golden samples for regression coverage.

