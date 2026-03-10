# Cognitive Staffing

A bilingual **Streamlit recruitment wizard** that turns unstructured job ads into a structured **NeedAnalysisProfile** and recruiter-ready outputs such as a job ad draft, interview guide, Boolean search, and exports.

**Live app**  
- https://cognitivestaffing.streamlit.app/

---

## What this project does

Cognitive Staffing helps recruiters and hiring teams move from messy input to a structured hiring brief:

1. **Ingest** a job ad from PDF, DOCX, URL, or pasted text
2. **Extract** structured data into the canonical `NeedAnalysisProfile`
3. **Guide** the user through a fixed bilingual wizard to validate and fill gaps
4. **Generate** recruiter-ready outputs and exports

This repository is designed around:

- a fixed **8-step wizard flow**
- a canonical **schema + model contract**
- bilingual **DE/EN** UI and generation behavior
- an **OpenAI Responses API** pipeline optimized for **GPT-5-nano**
- deterministic downstream outputs and exports

---

## Table of contents

- [Quickstart](#quickstart)
- [Architecture overview](#architecture-overview)
- [Wizard flow](#wizard-flow)
- [Repository map](#repository-map)
- [Configuration](#configuration)
- [OpenAI runtime rules](#openai-runtime-rules)
- [Development workflow](#development-workflow)
- [i18n and schema rules](#i18n-and-schema-rules)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

---

## Quickstart

### Requirements

- Python `>=3.11,<4.0`
- Poetry
- OpenAI API key

### 1) Clone and install

```bash
git clone https://github.com/KleinerBaum/cognitivestaffing.git
cd cognitivestaffing

python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

poetry install --with dev
2) Configure secrets

You can use either a local .env file or Streamlit secrets.

Option A — .env

Create a .env file in the repo root:

OPENAI_API_KEY=<your-key>
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_REQUEST_TIMEOUT=120

# Strict GPT-5-nano runtime
OPENAI_MODEL=gpt-5-nano
DEFAULT_MODEL=gpt-5-nano
LIGHTWEIGHT_MODEL=gpt-5-nano
MEDIUM_REASONING_MODEL=gpt-5-nano
HIGH_REASONING_MODEL=gpt-5-nano
STRICT_NANO_ONLY=true

# GPT-5-nano defaults
REASONING_EFFORT=minimal
VERBOSITY=low

# Optional guards / retrieval
OPENAI_TOKEN_BUDGET=12000
VECTOR_STORE_ID=
OPENAI_ORGANIZATION=
OPENAI_PROJECT=
Option B — .streamlit/secrets.toml
[openai]
OPENAI_API_KEY = "<set-in-runtime-or-secrets-manager>"
OPENAI_BASE_URL = "https://api.openai.com/v1"

OPENAI_MODEL = "gpt-5-nano"
DEFAULT_MODEL = "gpt-5-nano"
LIGHTWEIGHT_MODEL = "gpt-5-nano"
MEDIUM_REASONING_MODEL = "gpt-5-nano"
HIGH_REASONING_MODEL = "gpt-5-nano"

STRICT_NANO_ONLY = true
REASONING_EFFORT = "minimal"
VERBOSITY = "low"
OPENAI_REQUEST_TIMEOUT = 120
OPENAI_TOKEN_BUDGET = "12000"

VECTOR_STORE_ID = ""
OPENAI_ORGANIZATION = ""
OPENAI_PROJECT = ""
3) Run the app
poetry run streamlit run app.py
4) Verify the runtime

At minimum, confirm:

the app starts without missing-secret errors

extraction works from pasted text or a sample file

the wizard advances only when required fields are present

generated outputs still render and export correctly

logs show gpt-5-nano as the resolved model for non-embedding tasks

Architecture overview
High-level flow
Input (PDF / DOCX / URL / text)
  -> ingest / parsing
  -> structured extraction
  -> schema validation
  -> JSON repair / retry if needed
  -> NeedAnalysisProfile
  -> wizard review + gap filling
  -> generators / exports / artifacts
Core design principles

Schema-first: the canonical schema drives extraction, validation, UI behavior, and exports

Responses-first: OpenAI integrations should use the Responses API by default

Nano-only runtime: all non-embedding generation tasks should resolve to gpt-5-nano

Bilingual consistency: DE and EN labels, follow-ups, and generation outputs must stay aligned

Reviewable UX: the wizard must make known vs missing information obvious and editable

Wizard flow

The wizard has a fixed 8-step order:

Onboarding / Job Ad

Company

Team & Structure

Role & Tasks

Skills & Requirements

Compensation / Benefits

Hiring Process

Summary

UX contract

Every canonical step should follow the same structure:

Known — show what is already known, compact and readable

Missing — ask only what is still missing for that step

Validate — show required / critical gaps and enforce gating

Nav — Back / Next

Rules:

Navigation is linear: Back / Next

Next stays disabled until required fields for the current step are satisfied

AI tools must not compete with the main Missing form

Assistants belong in an expander or dedicated Tools area, not inline with required inputs

Repository map
Entry and routing

app.py — Streamlit entry point

wizard_router.py — step routing and navigation guards

wizard/navigation/ — navigation state and session/query sync

Wizard UI

wizard/ — canonical wizard implementation

wizard_pages/ — step definitions / metadata / legacy proxies

wizard_tools/ — assistant and tool panels

wizard/step_registry.py — canonical step ordering and renderers

wizard/step_layout.py — shared step layout helpers

sidebar/, ui_views/, components/, ui/ — shared UI elements

styles/, images/ — assets and styling

Data contract

schema/need_analysis.schema.json — canonical JSON schema

schemas.py, models/ — Pydantic/data models

Follow-up and missing-field logic

critical_fields.json — critical fields by step

question_logic.py, questions/ — follow-up orchestration

role_field_map.json — role-dependent priority mapping

wizard/services/followups.py — canonical follow-up generation

wizard/missing_fields.py — missing-field helpers

wizard/step_status.py — step-level status helpers

wizard/metadata.py — field ownership and step mapping

LLM, extraction, and pipelines

openai_utils/ — OpenAI client wrappers, payload assembly, retries

llm/ — prompt assembly, response schemas, JSON repair

pipelines/ — ingest -> extraction -> repair -> exports

ingest/, nlp/ — parsing and heuristics

prompts/ — prompt templates and prompt fragments

Outputs

generators/ — job ad, interview guide, Boolean search, summaries

exports/ — export wiring

artifacts/ — generated files and cached artifacts

Tests and tooling

tests/

pyproject.toml

pytest.ini

.env.example

AGENTS.md


ESCO API resilience and cache behavior

- ESCO calls use GET only (`https://ec.europa.eu/esco/api`) with request timeout plus retry/backoff for transient failures.
- Caching is intentionally split: `core/esco_utils.py` caches raw ESCO payloads, while `wizard/flow.py` caches only UI-ready projections (labels/rank metadata) to avoid duplicate raw-cache layers.
- ESCO cache keys are normalized with query/URI + language + limit + `ESCO_CACHE_API_VERSION` to avoid language mismatches across reruns.
- If ESCO is temporarily unavailable, the wizard surfaces a bilingual notice and falls back to local/offline suggestions.

Configuration
Required variables
Variable	Required	Purpose
OPENAI_API_KEY	Yes	OpenAI API authentication
OPENAI_BASE_URL	No	Custom / regional endpoint
OPENAI_REQUEST_TIMEOUT	No	Request timeout in seconds
STRICT_NANO_ONLY	Yes (recommended)	Enforce gpt-5-nano for all non-embedding tasks
OPENAI_MODEL	Yes	Primary generation model
DEFAULT_MODEL	Yes	Default routing model
LIGHTWEIGHT_MODEL	Yes	Lightweight tier model
MEDIUM_REASONING_MODEL	Yes	Medium tier model
HIGH_REASONING_MODEL	Yes	High tier model
REASONING_EFFORT	No	Default reasoning effort
VERBOSITY	No	Default output verbosity
OPENAI_TOKEN_BUDGET	No	Optional session/request budget guard
VECTOR_STORE_ID	No	Optional retrieval / RAG store
OPENAI_ORGANIZATION	No	Optional OpenAI org
OPENAI_PROJECT	No	Optional OpenAI project
Recommended defaults for this repo

For a strict nano-only runtime:

OPENAI_MODEL = gpt-5-nano

DEFAULT_MODEL = gpt-5-nano

LIGHTWEIGHT_MODEL = gpt-5-nano

MEDIUM_REASONING_MODEL = gpt-5-nano

HIGH_REASONING_MODEL = gpt-5-nano

STRICT_NANO_ONLY = true

REASONING_EFFORT = minimal

VERBOSITY = low

Retrieval

Set VECTOR_STORE_ID only if retrieval is enabled.
If it is empty, the app should run without RAG.

Task-specific overrides

If task routing overrides are supported in the codebase, they must still respect strict nano-only mode.
In other words: per-task tuning may change effort, verbosity, or token limits, but should not silently switch model families.

OpenAI runtime rules

This repo should follow these rules:

Use the Responses API by default

Use text.format for structured outputs

Use strict function schemas for callable application tools

Reuse previous_response_id in multi-turn / tool flows where appropriate

Keep prompts compact and explicit

Do not silently route to other model families

Do not request unsupported GPT-5-nano tools

GPT-5-nano guidance for this project

Use gpt-5-nano for:

extraction support

follow-up generation

recruiter helper text

job ad generation

interview guide generation

profile summaries

structured transformations

classification / normalization tasks

Prefer:

compact prompts

exact JSON / Markdown contracts

low verbosity

minimal reasoning effort as baseline

Avoid using model escalation as a band-aid for:

prompt drift

schema drift

weak validation

missing repair logic

UI / model key mismatches

Tooling policy

Allowed only if explicitly supported in the runtime path:

function calling

structured outputs

web search

file search

image generation

code interpreter

MCP (if intentionally integrated)

Do not introduce or rely on:

tool search

computer use

hosted shell

apply patch

skills

Development workflow
Local quality checks

Run these before opening a PR:

poetry run ruff format .
poetry run ruff check .
poetry run mypy .
poetry run pytest -q

For local app verification:

poetry run streamlit run app.py
Recommended branch naming

Use short, reviewable branches such as:

feat/nano-routing

fix/schema-propagation

refactor/followup-layout

docs/readme-refresh

Pull request expectations

Keep PRs small and cohesive.

A good PR should include:

problem statement

repro steps

expected vs actual behavior

files changed

verification commands

screenshots only if they add real value

notes on schema/i18n impact

notes on model/tool-routing impact

Agent / coding-assistant workflow

Before editing code, read:

AGENTS.md

README.md

the closest relevant module(s)

For model and prompt changes, inspect first:

config/

openai_utils/

llm/

prompts/

generators/

wizard/services/followups.py

i18n and schema rules
Bilingual rules

This project is bilingual (DE / EN).

Whenever you change:

labels

help text

validation text

warning text

follow-up phrasing

generated headings

summary/export wording

verify both languages.

Do not update only one language path unless the feature is explicitly language-specific.

Schema propagation rules

If you add, remove, rename, or move a field, propagate it across all affected layers:

schema/need_analysis.schema.json

schemas.py / models/

wizard/ / wizard_pages/ / ui_views/

question_logic.py / questions/ / wizard/services/followups.py

wizard/metadata.py

critical_fields.json

generators/ / exports/

tests

Do not leave dangling keys where:

schema != model != UI != followups != exports
Canonical field ownership

Keep missing prompts where their inputs live.

If field ownership changes, update:

step UI

step metadata

missing-field mapping

follow-up routing

tests

Troubleshooting
OPENAI_API_KEY missing

Symptoms:

startup failure

extraction/generation unavailable

authentication errors

Fix:

set OPENAI_API_KEY in .env or .streamlit/secrets.toml

restart the Streamlit app after changing secrets

Wrong model still appears in logs

Symptoms:

requests resolve to gpt-4o-mini, gpt-5-mini, o3-mini, or another non-nano model

Fix:

verify STRICT_NANO_ONLY=true

verify all tier variables point to gpt-5-nano

inspect config/models.py, llm/model_router.py, and llm/cost_router.py

search the repo for legacy model literals before assuming the config is enough

API timeouts

Symptoms:

slow generation

request timeout errors

repeated retries

Fix:

raise OPENAI_REQUEST_TIMEOUT if necessary

reduce prompt size

reduce output size

keep prompts contract-driven

avoid re-sending large conversation histories when previous_response_id can be reused

Structured output / schema errors

Symptoms:

invalid structured response

schema mismatch

JSON repair loops

parsing failures

Fix:

verify the schema matches the parser and the UI keys

keep output contracts explicit

use strict schemas for function tools

ensure Responses structured outputs are configured via text.format

inspect repair logs before changing models

Invalid schema for response_format

Symptoms:

bad request from OpenAI

schema rejected before generation

Fix:

remove legacy Chat-style response_format usage from Responses payloads

use Responses-compatible structured output configuration

compare required keys and properties carefully

inspect schema-generation and payload-assembly code together

missing ScriptRunContext

Symptoms:

Streamlit warnings during worker/background execution

Fix:

keep Streamlit UI/session-state mutations on the main thread

pass immutable payloads into background work

do not call Streamlit UI functions from worker threads

Telemetry / OTLP warning

Symptoms:

OTLP endpoint not configured

Fix:

set OTEL_EXPORTER_OTLP_ENDPOINT if telemetry is needed

otherwise ignore during local development

Dependency drift on Streamlit Cloud

Symptoms:

startup warnings

resolver conflicts

environment mismatch between local and deployed runs

Fix:

keep pyproject.toml and poetry.lock in sync

regenerate the lockfile when dependency constraints change

commit both files together

Contributing

Please keep changes:

small

reviewable

schema-safe

bilingual

testable

For all substantial changes:

update or add tests

preserve the wizard UX contract

preserve the schema contract

document any new config variables

update README.md and AGENTS.md when behavior changes

License

MIT. See LICENSE.
