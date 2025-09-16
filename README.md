# Vacalyser — AI Recruitment Need Analysis (Streamlit)

**Vacalyser** turns messy job ads into a **complete, structured profile**, then asks only the *minimal* follow‑ups. It enriches with **ESCO** (skills/occupations) and your **OpenAI Vector Store** to propose **missing skills, benefits, tools, and tasks**. Finally, it generates a polished **job ad**, **interview guide**, and **boolean search string**.

Vacalyser supports OpenAI’s cost-optimized `gpt-4o-mini` and flagship
`gpt-4o` models on compatible endpoints and falls back to the widely available
`gpt-3.5-turbo` by default. These newer models improve reasoning, support
JSON-mode structured output and tool calls, and deliver lower cost and
latency. They trade off a shorter context window and slightly lower language
fluency compared to full GPT‑4. The app communicates via the `responses.create`
API, enabling JSON schema validation and function/tool calling. Custom models
such as `gpt-4o-mini` require a specialized OpenAI/Azure endpoint and are not
available on standard OpenAI accounts.

## Highlights
- **Dynamic Wizard**: multi‑step, bilingual (EN/DE), low‑friction inputs with tabbed text/upload/URL choices and auto-start analysis
- **Restart option**: clicking "Done" returns to the first step to begin another profile
- **Manual entry option**: skip the upload step and start with an empty profile
- **Critical field checks**: wizard blocks navigation until essential fields are filled and highlights missing inputs inline
- **Extraction feedback**: review detected base data in a sidebar table with missing fields highlighted before continuing
- **Guided error messages**: clear hints when uploads or URLs fail
- **Improved URL parsing**: reports HTTP status on failures and trims boilerplate
- **Upfront language switch**: choose German or English before entering any data
- **Advantages page**: explore key benefits and jump straight into the wizard via a dedicated button
- **One‑hop extraction**: Parse PDFs/DOCX/TXT/URLs into 20+ fields
- **Robust base field extraction**: heuristics recover job title, company name and city when the model misses them
- **Structured output**: function calling/JSON mode ensures valid responses
- **Instant overview**: review extracted fields in a compact tabbed table before continuing
- **API helper**: `call_chat_api` wraps the OpenAI Responses API with tool and JSON schema support, automatically executing mapped tools and returning a unified `ChatCallResult`
- **Analysis tools**: built-in `get_salary_benchmark` and `get_skill_definition` functions can be invoked by the model for richer need analysis
- **Smart follow‑ups**: priority-based questions enriched with ESCO & RAG that dynamically cap the number of questions by field importance (now up to 12 by default), shown inline in relevant steps. Required fields are consistently marked with a red asterisk.
- **Persistent follow-up tracking**: answered or skipped questions are remembered and won't reappear when navigating back through the wizard.
- **Follow-up suggestion chips**: if the assistant proposes possible answers, they appear as one-click chips above the input field.
- **AI-powered benefit suggestions**: fetch common perks for the role/industry and add them to the profile with a single click.
- **Auto re‑ask loop**: optional toggle that keeps asking follow-up questions automatically until all critical fields are filled, with clear progress messages and a stop button for user control.
- **Token usage tracker**: displays input/output token counts in the summary step.
- **Reasoning effort control**: select low, medium, or high reasoning depth with an environment-variable default.
- **Role-aware extras**: automatically adds occupation-specific questions (e.g., programming languages for developers, campaign types for marketers, board certification for doctors, grade levels for teachers, design tools for designers, shift schedules for nurses, project management methodologies for project managers, machine learning frameworks for data scientists, accounting software for financial analysts, HR software for human resource professionals, engineering tools for civil engineers, cuisine specialties for chefs).
- **ESCO‑Power**: occupation classification + essential skill gaps
- **Offline-ready ESCO**: set `VACAYSER_OFFLINE=1` to use cached occupations and skills without API calls; data comes from `integrations/esco_offline.json` and covers common roles. Unknown titles log a warning and skip enrichment—update the JSON or unset the env var to fall back to the live ESCO API
- **Cached ESCO calls**: Streamlit caching avoids repeated API requests
- **Auto-filled skills**: essential ESCO skills merge into required skills; generic entries like "Communication" are ignored so follow-ups stay relevant
- **RAG‑Assist**: use your vector store to fill/contextualize *(requires setting `VECTOR_STORE_ID` and a populated vector store)*
- **Reasoning models**: uses cost-optimized `gpt-4o-mini`/`gpt-4o` on
  supported endpoints, falling back to `gpt-3.5-turbo` by default for the public
  API. The Responses API enables JSON mode and tool calling at lower cost/latency,
  albeit with shorter context and slightly lower fluency than full GPT‑4
- **Inline refinement**: adjust generated documents with custom instructions and instantly update the view
- **Robust error handling**: user-facing alerts for API or network issues
- **Cross-field deduplication**: avoids repeating the same information across multiple fields
- **Tabbed summary**: finalize all sections in inline-editable tabs and regenerate outputs instantly
- **Output tabs**: generated Job Ad, Boolean String and Interview Guide are organized in dedicated tabs
- **Missing info alerts**: highlights empty critical fields while allowing navigation so you can fix them later
- **Boolean Builder 2.0**: interactive search string with selectable skills and title synonyms
- **Export**: clean JSON profile, job‑ad markdown, interview guide
- **Customizable interview guides**: choose 3–10 questions, automatically covering responsibilities, culture, and specified hard and soft skills
- **Tone control**: pick formal, casual, creative, or diversity-focused styles for job ads and interview guides
- **Audience-specific guides**: tailor interview guides for general, technical, or HR interviewers
- **Comprehensive job ads**: generated ads now mention requirements, salary and work policy when provided
- **Employer branding**: company mission and culture flow into job ads and interview guides
- **Culture-aware interviews**: German guides automatically include a question on cultural fit when a company culture is specified
- **Mission & culture overview**: summary page highlights company mission and culture for quick reviewer context
- **Bias check**: flags potentially discriminatory terms and suggests inclusive alternatives in generated job ads
- **Onboarding Intro**: welcome step explains required inputs and allows skipping for returning users
- **Responsive layout**: mobile-friendly columns and touch-sized buttons
- **Salary analytics dashboard**: live sidebar estimate with optional factor explanations
- **Enhanced compensation step**: slider-based salary range, preset currency choices, bonus/commission details and common benefit suggestions
- **Branding options**: upload a company logo, provide style‑guide hints and toggle between dark and light themes
- **Glassmorphic theme**: browser-optimized design with a hero background
- **Expanded skills section**: distinguish must-have and nice-to-have hard/soft skills, plus certifications, language requirements, and tools & technologies
  - **Schema-aligned benefits**: benefit inputs bind directly to schema keys, merging health and retirement perks so all appear automatically
- **Company insights**: specify headquarters location, company size, brand and contact details for clearer context
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

4. **Configure environment variables**

   ```bash
   export OPENAI_API_KEY=sk-your-key
   # optional overrides
   export OPENAI_MODEL=gpt-4                  # e.g., gpt-3.5-turbo, gpt-4, gpt-4o-mini
   export REASONING_EFFORT=high               # low|medium|high (default: medium)
   export OPENAI_BASE_URL=http://localhost:8080/v1  # custom endpoint
   # optional: enable RAG suggestions via vector store
   export VECTOR_STORE_ID=vs_XXXXXXXXXXXXXXXXXXXXXXXX
   ```

5. **Launch the app**

   ```bash
   streamlit run app.py
   ```

Run `streamlit run app.py` to start the app locally and open the URL shown in your terminal.

If you run the app with a standard OpenAI API key, it will default to
`gpt-3.5-turbo`. Set `OPENAI_MODEL=gpt-4` for full GPT‑4 access. Custom mini
models such as `gpt-4o-mini` require a compatible OpenAI or Azure endpoint.

### Model selection & reasoning effort

Vacalyser auto-detects the endpoint: it uses `gpt-4o-mini` on compatible custom
deployments and `gpt-3.5-turbo` on the public API. Set `OPENAI_MODEL` or
`DEFAULT_MODEL` to `gpt-4o`, `gpt-4`, or any other supported model, and adjust
`REASONING_EFFORT` (`low`, `medium`, or `high`) for more or less
deliberate thinking:

```bash
export OPENAI_MODEL=gpt-4
export REASONING_EFFORT=low
```

The in-app selector lists currently supported Responses API chat models:
`gpt-4o-mini`, `gpt-4o`, `gpt-4.1-mini`, `gpt-4.1`, and `gpt-3.5-turbo`.
Legacy names such as `gpt-3.5-turbo-16k` or `gpt-5-nano` are no longer
available.

Set `OPENAI_BASE_URL` to point to a compatible endpoint if you are not using
the default OpenAI API URL.

### Configuration

Vacalyser reads API credentials from environment variables or [Streamlit
secrets](https://docs.streamlit.io/streamlit-community-cloud/get-started/deploy-an-app/secrets-management). At minimum,
define `OPENAI_API_KEY` before launching the app:

```bash
export OPENAI_API_KEY=sk-your-key
# optional overrides
export OPENAI_BASE_URL=https://api.openai.com/v1  # e.g., Azure/OpenAI responses endpoint
export OPENAI_MODEL=gpt-4
```

You can also place these values in `.streamlit/secrets.toml` under an `openai`
section, which the app reads automatically:

```toml
[openai]
OPENAI_API_KEY = "sk-your-key"
OPENAI_BASE_URL = "https://api.openai.com/v1"
OPENAI_MODEL = "gpt-4"
```

Other environment flags:

- `VACAYSER_OFFLINE=1` – use cached ESCO data from `integrations/esco_offline.json`
  to run without internet access to the ESCO API.
- `VECTOR_STORE_ID=vs_…` – enable OpenAI File Search for RAG (leave unset to
  disable).


### Optional: OCR for scanned PDFs

Vacalyser can perform OCR on PDF pages without embedded text. Install the
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

If `VECTOR_STORE_ID` is unset or empty, Vacalyser runs without RAG.

## Troubleshooting

- **"Missing OPENAI_API_KEY"** – ensure the environment variable is set or add it to `.streamlit/secrets.toml`.
- **"Model not found"** – check that `OPENAI_MODEL` is available on your endpoint.
- **Vector store errors** – set `VECTOR_STORE_ID` to a valid store ID and make sure the store contains documents.

## Known Limitations

- Relies on the OpenAI Responses API; accounts without access cannot run the app.
- `gpt-4o-mini` and other custom models require specialized OpenAI or Azure endpoints.
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

Vacalyser registers light-weight tools that the model can call via the
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

### Migration to the Responses API

The project was refactored from the deprecated Chat Completions endpoint to
`responses.create`. This brings JSON schema validation and explicit
function/tool calling. Legacy model flags were removed, and older model options
are no longer supported.
Prompt behaviours may differ slightly due to the new reasoning models.

## Changelog

See [docs/CHANGELOG.md](docs/CHANGELOG.md) for recent changes.
