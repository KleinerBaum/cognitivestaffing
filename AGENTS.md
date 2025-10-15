# Autonomous Agents in Cognitive Staffing

This guide documents every autonomous or semi-autonomous agent that powers Cognitive Staffing. Use it to understand how data flows through the system, which credentials are required, and where to extend or replace behaviour.

## Configuration
All agents rely on OpenAI credentials supplied either through environment variables or `st.secrets["openai"]`:

- `OPENAI_API_KEY` – mandatory for all LLM calls.
- `OPENAI_BASE_URL` – optional override (set to `https://eu.api.openai.com/v1` for EU hosting).
- `OPENAI_MODEL` – optional default model. The router still picks `gpt-5.1-mini` (GPT-5 mini) / `gpt-5.1-nano` (GPT-5 nano) per task unless overridden.
- `OPENAI_REQUEST_TIMEOUT` – optional request timeout in seconds (defaults to 120s for long-running generations).
- `VECTOR_STORE_ID` – optional OpenAI Vector Store used by RAG-enabled agents via the `file_search` tool.
- `VACAYSER_OFFLINE` – set to `1` to load the local ESCO cache instead of calling the public API.

Additional environment hints:
- `OCR_BACKEND` toggles OCR/vision extraction (`none` or `openai`).
- OpenTelemetry variables (`OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_SERVICE_NAME`) enable tracing for each agent call.

## Core Agents

### 1. Follow-up Question Generator (FQG)
- **Purpose:** Turn a partially filled vacancy JSON into a short list of prioritized follow-up questions. Priorities are `critical`, `normal`, or `optional`, and suggested answers fuel the chip UI.
- **Inputs:** Current vacancy profile (`extracted`), locale (`lang`), optional ESCO payload, optional RAG suggestions.
- **Outputs:** `{ "questions": [ { field, question, priority, suggestions } ] }` enforced via `json_schema` in the Responses API.
- **Model & tools:** `gpt-5.1-nano` (GPT-5 nano) via `responses.create` (JSON mode). Uses `file_search` automatically if `VECTOR_STORE_ID` is present.
- **When it runs:** After the initial extraction and whenever the user triggers the follow-up step (manual rerun or Auto re-ask loop).

### 2. ESCO Enricher
- **Purpose:** Normalize the job title with ESCO, retrieve essential skills, and highlight gaps in the current profile. Also produces normalized skill labels for the UI.
- **Inputs:** `job_title`, `lang`, and current requirements.
- **Outputs:** Occupation metadata (`preferredLabel`, group, URI), `essential_skills`, `missing_esco_skills`, and label mapping.
- **Model & tools:** Calls the ESCO REST API (occupation classification + skill lookup). No LLM cost when ESCO is disabled or offline.
- **When it runs:** During extraction, when job titles change, and while generating skill suggestions.

### 3. RAG Completion Agent
- **Purpose:** Retrieve supporting snippets from the configured OpenAI vector store to pre-fill missing fields or offer better suggestion candidates.
- **Inputs:** Vacancy context (title, seniority, existing JSON) and list of missing fields.
- **Outputs:** `rag_suggestions` mapping each missing field to candidate values plus optional rationales.
- **Model & tools:** `gpt-5.1-nano` (GPT-5 nano) with the `file_search` tool against `VECTOR_STORE_ID`.
- **When it runs:** Before the FQG (to seed follow-up chips) and on-demand when the user clicks “Refresh suggestions”.

### 4. Company Intel Agent
- **Purpose:** Extract company name, location, mission, and culture directly from a provided URL. The ingest layer fetches HTML/PDF content; the agent distills it into structured data.
- **Inputs:** `company_url` plus fetched page text.
- **Outputs:** `{ company_name, location, company_mission, company_culture }`.
- **Model & tools:** `gpt-5.1-mini` (GPT-5 mini) via structured extraction prompts.
- **When it runs:** When a user provides a company URL or triggers “Fetch from website”.

### 5. Suggestion Helpers
Small focused agents that enrich the vacancy profile:
- **Task Suggester:** Drafts responsibilities per role.
- **Skill Suggester:** Generates hard/soft skills (with ESCO normalization when available).
- **Benefit Suggester:** Combines curated lists and LLM ideas for perks.
- **Boolean Query Builder:** Produces a recruiter-friendly boolean search string.
- **Interview Guide Generator:** Delivers structured interview questions and rubrics (supports streaming).
- **Job-ad Writer:** Streams a Markdown job ad aligned with selected tone and branding cues.

All helpers use the Responses API: long-form outputs (`job_ad`, `interview_guide`, `boolean_query`) call `gpt-5.1-mini` (GPT-5 mini) with streaming; shorter lists (`skills`, `benefits`, `tasks`) run on `gpt-5.1-nano` (GPT-5 nano).

### 6. Auto Re-ask Loop
- **Purpose:** Automatically re-trigger the FQG until every `critical` question is answered, reducing manual intervention.
- **Inputs:** Current profile (`st.session_state[profile]`), language, optional vector store context.
- **Outputs:** Same schema as the FQG (updated questions) plus state updates marking which questions are resolved.
- **Model & tools:** Delegates to the FQG.
- **When it runs:** When the “Auto follow-ups” toggle is active after extraction or after each auto-answer.

## Compliance & Forthcoming Agents

### Compliance Sentinel *(planned)*
- **Goal:** Review generated content (job ads, interview guides, follow-ups) for GDPR/EEO compliance and risky phrasing.
- **Behaviour:** Receives structured outputs plus metadata (jurisdiction, language). Flags violations, proposes safe rewrites, and can block downstream exports. Integrates with Deliberative Alignment routines in `llm/responses.py` to ensure refusal reasons reach the UI.
- **Model & tools:** Planned for `gpt-5.1-mini` (GPT-5 mini) with policy-specific prompt templates and optional audit logging via OpenTelemetry attributes.

### Tech-Stack Miner *(planned)*
- **Goal:** Detect missing technologies, frameworks, and tools relevant to the vacancy based on industry, ESCO data, and vector store snippets.
- **Behaviour:** Combines deterministic heuristics (mapping tables in `skill_market_insights.json`) with LLM reasoning to propose stack items grouped by category (languages, frameworks, DevOps, data). Outputs structured JSON for direct injection into requirement sections.
- **Model & tools:** Will route through `gpt-5.1-nano` (GPT-5 nano) for quick classifications and escalate ambiguous cases to `gpt-5.1-mini` (GPT-5 mini). May optionally trigger additional vector store searches to justify suggestions.

### DEI Language Auditor *(planned)*
- **Goal:** Highlight non-inclusive or biased phrasing in job ads and interview questions, suggesting neutral alternatives.
- **Behaviour:** Runs as a post-processing step on generated text. Returns annotations with severity levels so the UI can surface inline highlights.

### Content Cost Router *(planned)*
- **Goal:** Dynamically choose between `gpt-5.1-mini` (GPT-5 mini) and `gpt-5.1-nano` (GPT-5 nano) depending on prompt complexity, context size, and required output length, keeping usage predictable.
- **Behaviour:** Extends the dispatcher in `config.py`, logging routing decisions for analytics and enabling per-step overrides from the settings panel.

---
Every agent returns a unified `ChatCallResult` (OK/usage/error/raw). UI components translate errors into friendly alerts with retry buttons, and exponential backoff protects against transient rate limits. Refer to `llm/` for implementation details and `wizard.py` for integration points.
