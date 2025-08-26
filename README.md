# Vacalyser — AI Recruitment Need Analysis (Streamlit)

**Vacalyser** turns messy job ads into a **complete, structured vacancy profile**, then asks only the *minimal* follow‑ups. It enriches with **ESCO** (skills/occupations) and your **OpenAI Vector Store** to propose **missing skills, benefits, tools, and tasks**. Finally, it generates a polished **job ad**, **interview guide**, and **boolean search string**.

## Highlights
- **Dynamic Wizard**: multi‑step, bilingual (EN/DE), low‑friction inputs with tabbed text/upload/URL choices and auto-start analysis
- **Advantages page**: explore key benefits and jump straight into the wizard via a dedicated button
- **One‑hop extraction**: Parse PDFs/DOCX/URLs into 20+ fields
- **Structured output**: function calling/JSON mode ensures valid responses
- **Instant overview**: review extracted fields in a compact tabbed table before continuing
- **API helper**: `call_chat_api` now returns a unified `ChatCallResult` and supports OpenAI function calls for reliable extraction
- **Smart follow‑ups**: priority-based questions enriched with ESCO & RAG that dynamically cap the number of questions by field importance (now up to 12 by default), shown inline in relevant steps. Critical questions are highlighted with a red asterisk.
- **Auto re‑ask loop**: optional toggle that keeps asking follow-up questions automatically until all critical fields are filled, with clear progress messages and a stop button for user control.
- **Role-aware extras**: automatically adds occupation-specific questions (e.g., programming languages for developers, campaign types for marketers, board certification for doctors, grade levels for teachers, design tools for designers, shift schedules for nurses, project management methodologies for project managers, machine learning frameworks for data scientists, accounting software for financial analysts, HR software for human resource professionals, engineering tools for civil engineers, cuisine specialties for chefs).
- **ESCO‑Power**: occupation classification + essential skill gaps
- **Offline-ready ESCO**: set `VACAYSER_OFFLINE=1` to use cached occupations and skills without API calls
- **Cached ESCO calls**: Streamlit caching avoids repeated API requests
- **RAG‑Assist**: use your vector store to fill/contextualize
- **Cost‑aware**: GPT‑3.5 by default and minimal re‑asks
- **Model**: optimized for GPT‑3.5 for suggestions and outputs
- **Inline refinement**: adjust generated documents with custom instructions and instantly update the view
- **Robust error handling**: user-facing alerts for API or network issues
- **Cross-field deduplication**: avoids repeating the same information across multiple fields
- **Tabbed summary**: collected fields are editable in stage-based tabs for faster review
- **Missing info alerts**: highlights empty critical fields and blocks navigation until they're filled, letting you jump back to fix them
- **Boolean Builder 2.0**: interactive search string with selectable skills and title synonyms
- **Export**: clean JSON profile, job‑ad markdown, interview guide
- **Customizable interview guides**: choose 3–10 questions, automatically covering responsibilities, culture, and specified hard and soft skills
- **Tone control**: pick formal, casual, creative, or diversity-focused styles for job ads and interview guides
- **Comprehensive job ads**: generated ads now mention requirements, salary and work policy when provided
- **Employer branding**: company mission and culture flow into job ads and interview guides
- **Culture-aware interviews**: German guides automatically include a question on cultural fit when a company culture is specified
- **Mission & culture overview**: summary page highlights company mission and culture for quick reviewer context
- **Bias check**: flags potentially discriminatory terms and suggests inclusive alternatives in generated job ads
- **Onboarding Intro**: welcome step explains required inputs and allows skipping for returning users
- **Responsive layout**: mobile-friendly columns and touch-sized buttons
- **Salary analytics dashboard**: live sidebar estimate with optional factor explanations
- **Branding options**: upload a company logo, provide style‑guide hints and toggle between dark and light themes
- **Glassmorphic theme**: browser-optimized design with a hero background
- **Expanded skills section**: enter certifications, language requirements, and tools & technologies alongside hard and soft skills
  - **Schema-aligned benefits**: benefit inputs bind directly to schema keys, merging health and retirement perks so all appear automatically
- **Company insights**: specify headquarters location and company size for clearer context
- **Domain-specific suggestions**: built-in lists of programming languages, frameworks, databases, cloud providers and DevOps tools help guide inputs
- **LLM skill proposals**: AI suggests relevant hard skills, soft skills and IT technologies based on the job title

---

## Quick Start

Requires **Python 3.11 or 3.12**.

```bash
git clone https://github.com/KleinerBaum/cognitivestaffing
cd cognitivestaffing

# create and activate a virtual environment (pick one Python version)
python3.11 -m venv .venv  # or: python3.12 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt  # or: pip install -e .
streamlit run app.py
```

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

## Configuration

Core JSON schemas like `schema/need_analysis.schema.json`, `critical_fields.json`,
`tone_presets.json` and `role_field_map.json` are loaded via
`config_loader.load_json`, which falls back to safe defaults and logs a warning
if a file is missing or malformed.

The vacancy profile schema does not enforce any required properties; every field
is optional and may be omitted.

## Session State & Migration

Session keys are centralized in `constants/keys.py`. Business data uses flat
keys from `StateKeys` such as `profile_data` or `jd_raw_text`, while widget
"shadow" keys come from `UIKeys` like `ui.jd_text_input`. Legacy entries like
`data.jd_text` or plain `jd_text` are migrated to the new schema on startup so
existing drafts remain intact.
