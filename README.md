# Cognitive Needs — AI Recruitment Need Analysis (Streamlit)

**Cognitive Needs** turns messy job ads into a **complete, structured profile**, then asks only the *minimal* follow‑ups. It integrates with your **OpenAI Vector Store** to propose **missing skills, benefits, tools, and tasks**. ESCO-based occupation and skill enrichment is currently disabled and hidden in the wizard. Finally, the app generates a polished **job ad**, **interview guide**, and **boolean search string**.

Cognitive Needs routes tasks across OpenAI’s GPT‑5 family to balance quality
and cost. `gpt-5-mini` powers extraction, document generation and other
reasoning-heavy flows, while `gpt-5-nano` handles fast list suggestions and
heuristics. Embeddings and vector search use `text-embedding-3-small`. All LLM
calls use the Responses API (`responses.create`) with JSON schema validation
and function/tool calling. Set `OPENAI_MODEL` or the in-app selector to override
the base model if needed.

## Highlights
- **Dynamic Wizard**: multi‑step, bilingual (EN/DE), low‑friction inputs with tabbed text/upload/URL choices and auto-start analysis
- **Restart option**: clicking "Done" returns to the first step to begin another profile
- **Manual entry option**: skip the upload step and start with an empty profile
- **Critical field checks**: wizard blocks navigation until essential fields are filled and highlights missing inputs inline
- **Extraction feedback**: review detected base data in a sidebar table with missing fields highlighted before continuing
- **Confidence legend**: inline icons explain which fields came from rule-based matches (🔎) versus AI inference (🤖) and whether they are locked until manually unlocked
- **Contextual sidebar**: step-aware cards show the most relevant company, role, requirements and process data alongside a live progress tracker
- **Salary expectation widget**: trigger an on-demand benchmark that compares the refreshed range with your entered salary data directly in the sidebar
- **Guided error messages**: clear hints when uploads or URLs fail
- **Improved URL parsing**: reports HTTP status on failures and trims boilerplate
- **Upfront language switch**: choose German or English before entering any data
- **Advantages page**: explore key benefits and jump straight into the wizard via a dedicated button
- **Legal information page**: centralises imprint, ESCO licence notice and disclaimers for compliant launches
- **One‑hop extraction**: Parse PDFs/DOCX/TXT/URLs into 20+ fields
- **Robust base field extraction**: heuristics recover job title, company name and city when the model misses them
- **NER-backed location fallback**: shared spaCy pipeline fills missing city/country data in German postings when regex fails
- **Canonical geo/language normalisation**: pycountry-backed mapper standardises German country and language inputs (Deutschland→Germany, Deutsch→German) and deduplicates case variants
- **Structured output**: function calling/JSON mode ensures valid responses
- **In-house validation loop**: our custom validator replays the extraction through the `NeedAnalysisProfile` schema, retrying with guard-rails and falling back to raw JSON mode when the model drifts
- **Job posting schema**: `schema/job_posting_extraction.schema.json` validates 20+ required vacancy fields for consistent LLM outputs
- **Instant overview**: review extracted fields in a compact tabbed table before continuing
- **API helper**: `call_chat_api` wraps the OpenAI Responses API with tool and JSON schema support, automatically executing mapped tools and returning a unified `ChatCallResult`; `stream_chat_api` uses `responses.stream` for token-level updates powering the job-ad UI
- **Analysis tools**: built-in `get_salary_benchmark` and `get_skill_definition` functions can be invoked by the model for richer need analysis
- **Smart follow‑ups**: priority-based questions that leverage RAG suggestions and dynamically cap the number of questions by field importance (now up to 12 by default), shown inline in relevant steps. Required fields are consistently marked with a red asterisk.
- **Persistent follow-up tracking**: answered or skipped questions are remembered and won't reappear when navigating back through the wizard.
- **Follow-up suggestion chips**: if the assistant proposes possible answers, they appear as one-click chips above the input field.
- **AI-powered benefit suggestions**: fetch common perks for the role/industry and add them to the profile with a single click.
- **Auto re‑ask loop**: optional toggle that keeps asking follow-up questions automatically until all critical fields are filled, with clear progress messages and a stop button for user control.
- **Token usage tracker**: displays input/output token counts per task in the summary step and sidebar.
- **Reasoning effort control**: select low, medium, or high reasoning depth with an environment-variable default.
- **ESCO features disabled**: occupation classification, essential skill enrichment, and role-specific prompts are currently turned off and hidden in the wizard.
- **RAG‑Assist**: use your vector store to fill/contextualize *(requires setting `VECTOR_STORE_ID` and a populated vector store)*
- **Model routing**: automatically dispatches calls to `gpt-5-mini` for
  extraction, job ads, interview guides and refinements, and to `gpt-5-nano`
  for cost-sensitive suggestion flows. Embeddings rely on
  `text-embedding-3-small`, all via the OpenAI Responses API with JSON schema
  and tool support.
- **Inline refinement**: adjust generated documents with custom instructions and instantly update the view
- **Robust error handling**: user-facing alerts for API or network issues
- **Cross-field deduplication**: avoids repeating the same information across multiple fields
- **Tabbed summary**: finalize all sections in inline-editable tabs and regenerate outputs instantly
- **Output workspace**: generated job ad, Boolean builder, and interview guide live in dedicated summary panels for quick iteration
- **Missing info alerts**: highlights empty critical fields while allowing navigation so you can fix them later
- **Boolean Builder 2.0**: dedicated panel with toggles for skills/title synonyms, instant query preview, and one-click download
- **Export**: clean JSON profile (summary header download button), job‑ad markdown, interview guide
- **Customizable interview guides**: choose 3–10 questions, automatically covering responsibilities, culture, and specified hard and soft skills
- **LLM-validated interview guides**: generation now routes through the GPT-5 mini Responses API with JSON schema validation while keeping a deterministic offline fallback
- **Tone control**: pick formal, casual, creative, or diversity-focused styles for job ads and interview guides
- **Audience-specific guides**: tailor interview guides for general, technical, or HR interviewers
- **Comprehensive job ads**: generated ads now mention requirements, salary and work policy when provided
- **Employer branding**: company mission and culture flow into job ads and interview guides
- **Culture-aware interviews**: German guides automatically include a question on cultural fit when a company culture is specified
- **Mission & culture overview**: summary page highlights company mission and culture for quick reviewer context
- **Bias check**: flags potentially discriminatory terms and suggests inclusive alternatives in generated job ads
- **Onboarding Intro**: welcome step explains required inputs and allows skipping for returning users
- **Responsive layout**: mobile-friendly columns and touch-sized buttons
- **Enhanced compensation step**: slider-based salary range, preset currency choices, bonus/commission details and common benefit suggestions
- **Branding options**: upload a company logo, provide style‑guide hints and toggle between dark and light themes
- **Glassmorphic theme**: browser-optimized design with a hero background
- **Expanded skills section**: distinguish must-have and nice-to-have hard/soft skills, plus certificates, language requirements, and tools & technologies
  - **Schema-aligned benefits**: benefit inputs bind directly to schema keys, merging health and retirement perks so all appear automatically
- **Company insights**: specify headquarters location, company size, brand and contact details for clearer context
- **Smart autofill suggestions**: accept or dismiss HQ/location and contact name proposals derived from other inputs, with opt-out memory
- **Detailed role setup**: capture desired start date, direct reports, contract type and optional KPIs or key projects via an expandable section
- **Process mapping**: plan stakeholders, per-stage details and application instructions directly in the wizard
- **Domain-specific suggestions**: built-in lists of programming languages, frameworks, databases, cloud providers and DevOps tools help guide inputs
- **LLM skill proposals**: AI suggests relevant hard skills, soft skills and IT technologies based on the job title

---

## Quick Start

Requires **Python 3.11 or 3.12**.

1. **Clone the repository and enter it**

   ```bash
   git clone https://github.com/KleinerBaum/cognitivestaffing
   cd cognitivestaffing
   ```

2. **Create and activate a virtual environment**

   ```bash
   python3.11 -m venv .venv  # or: python3.12 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt  # or: pip install -e .
   ```

   This installs spaCy together with the German `de_core_news_sm` model used for
   rule fallback of city/country detection. Ensure your environment picks up
  **OpenAI Python SDK ≥ 1.40.0**, which adds the Responses `text.format`
  JSON schema implementation required for our structured extraction flow.

4. **Configure environment variables**

   ```bash
   export OPENAI_API_KEY=sk-your-key
   # optional overrides
   export OPENAI_MODEL=gpt-5-mini             # e.g., gpt-5-mini, gpt-5-nano
   export REASONING_EFFORT=high               # low|medium|high (default: medium)
   export OPENAI_BASE_URL=http://localhost:8080/v1  # custom endpoint
   # optional: enable RAG suggestions via vector store
   export VECTOR_STORE_ID=vs_XXXXXXXXXXXXXXXXXXXXXXXX
   # optional: enable OpenTelemetry tracing (requires explicit endpoint)
   export OTEL_EXPORTER_OTLP_ENDPOINT=https://otel-collector.example.com/v1/traces
   export OTEL_SERVICE_NAME=cognitive-needs
   ```

5. **Launch the app**

   ```bash
   streamlit run app.py
   ```

Run `streamlit run app.py` to start the app locally and open the URL shown in your terminal.

With a standard OpenAI API key, the app defaults to `gpt-5-mini`. Set
`OPENAI_MODEL` to another Responses-compatible chat model if you need to force
an alternative. Legacy `gpt-4o` and `gpt-4o-mini` values (including dated
suffixes) are remapped automatically to the new GPT-5 equivalents so older
deployments keep working without manual intervention.

### Model selection & reasoning effort

Cognitive Needs now routes calls through a dispatcher: `gpt-5-mini` powers
extraction, refinements and content generation, while `gpt-5-nano` handles
cost-sensitive suggestion flows. Set `OPENAI_MODEL` or `DEFAULT_MODEL` if you
need to force a different Responses-compatible chat model, and adjust
`REASONING_EFFORT` (`low`, `medium`, or `high`) for more or less deliberate
thinking:

```bash
export OPENAI_MODEL=gpt-5-mini
export REASONING_EFFORT=low
```

The in-app selector offers three options:

- **Automatisch: GPT-5 (empfohlen)** – uses the dispatcher to pick `gpt-5-mini`
  or `gpt-5-nano` per task.
- **Force GPT-5 mini** – forces `gpt-5-mini` for every request.
- **Force GPT-5 nano** – forces `gpt-5-nano` for every request.

Set `OPENAI_BASE_URL` to point to a compatible endpoint if you are not using
the default OpenAI API URL.

### Configuration

Cognitive Needs reads API credentials from environment variables or [Streamlit
secrets](https://docs.streamlit.io/streamlit-community-cloud/get-started/deploy-an-app/secrets-management). At minimum,
define `OPENAI_API_KEY` before launching the app:

#### OpenTelemetry tracing (opt-in)

Telemetry is disabled unless you configure an OTLP collector endpoint. Set
`OTEL_EXPORTER_OTLP_ENDPOINT` to your collector URL (for example,
`https://otel-collector.example.com/v1/traces`) and, optionally, define
`OTEL_SERVICE_NAME` to customise the reported service identifier. Without an
explicit endpoint the app skips tracer initialisation, so no telemetry data is
sent by default.

```bash
export OPENAI_API_KEY=sk-your-key
# optional overrides
export OPENAI_BASE_URL=https://api.openai.com/v1  # e.g., Azure/OpenAI responses endpoint
export OPENAI_MODEL=gpt-5-mini
```

You can also place these values in `.streamlit/secrets.toml` under an `openai`
section, which the app reads automatically:

```toml
[openai]
OPENAI_API_KEY = "sk-your-key"
OPENAI_BASE_URL = "https://api.openai.com/v1"
OPENAI_MODEL = "gpt-5-mini"
```

Other environment flags:

- `VACAYSER_OFFLINE` – set to `1` to force the cached ESCO dataset and skip
  outbound API calls.
- `VECTOR_STORE_ID=vs_…` – enable OpenAI File Search for RAG (leave unset to
  disable).

#### ESCO offline cache

The offline fallback stored in `integrations/esco_offline.json` ships with the
**ESCO dataset v1.1.1** snapshot downloaded on **2025-10-09**. The source of
truth is the official download portal at
<https://esco.ec.europa.eu/en/use-esco/download>. Operators should check that
page at least quarterly (and after every Commission release announcement) to
refresh the cache so that local lookups stay aligned with the public API.


### Telemetry & tracing (optional)

Set the following environment variables to enable OpenTelemetry tracing. The app
configures an OTLP exporter on startup when an endpoint is provided and emits
spans for key LLM flows.

| Variable | Purpose |
| --- | --- |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OTLP collector endpoint (e.g. `https://otel.example.com/v1/traces`). |
| `OTEL_EXPORTER_OTLP_PROTOCOL` | Protocol to use (`http/protobuf` or `grpc`). Defaults to HTTP. |
| `OTEL_EXPORTER_OTLP_HEADERS` | Comma-separated `key=value` headers to include with each export. |
| `OTEL_EXPORTER_OTLP_TIMEOUT` | Export timeout in seconds. |
| `OTEL_EXPORTER_OTLP_CERTIFICATE` | Path to a CA bundle for custom TLS trust. |
| `OTEL_EXPORTER_OTLP_INSECURE` | Set to `1` to allow insecure gRPC connections. |
| `OTEL_SERVICE_NAME` | Logical service name reported with spans. Defaults to `cognitive-needs`. |
| `OTEL_TRACES_ENABLED` | Set to `0`/`false` to disable tracing without removing other settings. |
| `OTEL_TRACES_SAMPLER` | Sampler name (`parentbased_traceidratio`, `traceidratio`, `always_on`, `always_off`). |
| `OTEL_TRACES_SAMPLER_ARG` | Sampler argument (e.g. `0.25` for a 25% sampling ratio). |

Tracing is off by default; configure at least `OTEL_EXPORTER_OTLP_ENDPOINT` to
start emitting spans. Both OTLP/HTTP and OTLP/gRPC exporters are supported.


### Optional: OCR for scanned PDFs

Cognitive Needs can perform OCR on PDF pages without embedded text. Install the
dependencies and corresponding system packages:

```bash
pip install pdf2image pytesseract
# Debian/Ubuntu
sudo apt-get install poppler-utils tesseract-ocr
```

### Optional: RAG vector store

To enable retrieval-augmented suggestions, create an OpenAI vector store and
set the environment variable `VECTOR_STORE_ID` to its ID:

```bash
export VECTOR_STORE_ID=vs_XXXXXXXXXXXXXXXXXXXXXXXX
```

If `VECTOR_STORE_ID` is unset or empty, Cognitive Needs runs without RAG.

## Troubleshooting

- **"Missing OPENAI_API_KEY"** – ensure the environment variable is set or add it to `.streamlit/secrets.toml`.
- **"Model not found"** – check that `OPENAI_MODEL` is available on your endpoint.
- **Vector store errors** – set `VECTOR_STORE_ID` to a valid store ID and make sure the store contains documents.

## Known Limitations

- Relies on the OpenAI Responses API; accounts without access cannot run the app.
- `gpt-5-mini` and `gpt-5-nano` require the OpenAI Responses API (or Azure equivalents).
- RAG suggestions only work when a populated OpenAI vector store is configured.

## Config Files

Core JSON schemas like `schema/need_analysis.schema.json`, `critical_fields.json`,
`tone_presets.json` and `role_field_map.json` are loaded via
`config_loader.load_json`, which falls back to safe defaults and logs a warning
if a file is missing or malformed.

The profile schema lists all properties as required so the LLM always
returns every key, yet each field accepts ``null`` when information is
missing.

## Built-in Analysis Tools

Cognitive Needs registers light-weight tools that the model can call via the
Responses API:

- `get_salary_benchmark(role, country="US")` – returns an illustrative annual
  salary range for a role and country. No external API keys are required.
- `get_skill_definition(skill)` – provides a short definition for a given skill
  to help clarify requirements.

These tools enrich extraction and follow‑up questions during the need analysis
process.

## Session State & Migration

Session keys are centralized in `constants/keys.py`. Business data uses flat
keys from `StateKeys` such as `profile_data` or `profile_raw_text`, while widget
"shadow" keys come from `UIKeys` like `ui.profile_text_input`. Legacy entries like
`data.jd_text` or plain `jd_text` are migrated to the new schema on startup so
existing drafts remain intact.

## Development Notes

### Schema regeneration

The persisted need analysis schema is derived from the Pydantic models in
`models/need_analysis.py`. Run `python -m cli.generate_schema` after updating the
models to refresh `schema/need_analysis.schema.json` with the normalised output.
This keeps all nested `required` arrays (including `process.phases.task_assignments`)
aligned with the model definitions for Responses API validation.

### Migration to the Responses API

The project was refactored from the deprecated Chat Completions endpoint to
`responses.create`. This brings JSON schema validation and explicit
function/tool calling. Legacy model flags were removed, and older model options
are no longer supported.
Prompt behaviours may differ slightly due to the new reasoning models.

Recent platform updates folded the former Assistants features into the
Responses API. Cognitive Needs now:

- **avoids server-managed assistants/threads** – each request passes the full
  message history when needed so calls stay stateless by default.
- **defines tools directly on `responses.create` calls** via the helper in
  `openai_utils.api`, matching the new `tools=[...]` contract.
- **uses conversations only when explicit state is required**, keeping the
  Responses integration lightweight and future-proof.

## Changelog

See [docs/CHANGELOG.md](docs/CHANGELOG.md) for recent changes.
