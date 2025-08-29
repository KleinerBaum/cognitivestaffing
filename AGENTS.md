# Vacalyser — Autonomous Agents

This document lists all current and planned autonomous agents in Vacalyser, along with their roles and interfaces. Each agent is small, focused, and composable. *Note: earlier docs used the labels “GPT‑4o” and “GPT‑4o‑mini”; in code these map to OpenAI’s cost-optimized `gpt-5-nano` and `gpt-4.1-nano` models respectively.*

---

## Configuration

All agents depend on OpenAI credentials provided via environment variables or
`st.secrets["openai"]`:

- `OPENAI_API_KEY` – required API key for all LLM calls.
- `OPENAI_BASE_URL` – optional custom endpoint (e.g., Azure or Responses API).
- `OPENAI_MODEL` – optional default model override.
- `VECTOR_STORE_ID` – optional vector store ID enabling the RAG Completion Agent
  and enriching follow-up suggestions via the File Search tool.
- `VACAYSER_OFFLINE` – set to `1` to use the cached ESCO dataset and skip
  network calls.

---

## 1) Follow‑Up Question Generator (FQG)

**Purpose**  
Turn a partially filled vacancy JSON into a minimal, targeted list of follow-up questions that close all information gaps with the fewest user interactions.

**Inputs**  
- `extracted`: dict (current vacancy JSON)  
- `lang`: "en" | "de"  
- ESCO context (occupation, essential skills)  
- RAG suggestions (per field, optional)

**Outputs**  
- `questions`: list of objects, each with:  
  - `field`: schema key (or "")  
  - `question`: localized string  
  - `priority`: "critical" | "normal" | "optional"  
  - `suggestions`: list[str] (optional, to render as answer chips)

**Model / APIs**
- OpenAI Responses API with `gpt-5-nano` / `gpt-4.1-nano` (JSON schema + tool calling)
- ESCO API (occupation + essential skills lookup)
- Optional File Search tool using `vector_store_id` for context suggestions

**When**
- After initial extraction
- After each user update (optional re‑ask triggered or via Auto Re‑ask Loop)

---

## 2) ESCO Enricher

**Purpose**  
Normalize the role context and surface **missing essential skills** via ESCO; also standardize skill labels.

**Inputs**  
- `job_title`, `lang`  
- Existing lists (requirements, responsibilities, tools)

**Outputs**  
- `occupation`: {preferredLabel, group, uri}  
- `essential_skills`: list[str]  
- `missing_esco_skills`: list[str]  
- Normalized labels for suggested skills

**Model / APIs**  
- ESCO REST API (occupation match + skill relations)

**When**  
- During initial extraction & FQG  
- When suggesting skills/tasks in later steps

---

## 3) RAG Completion Agent

**Purpose**
Fill or propose values for missing fields using your **OpenAI vector store** (set via `VECTOR_STORE_ID`; omit or leave empty to disable). Suggestions feed into FQG’s `suggestions` field.

**Inputs**  
- Job context (title, industry, current JSON)  
- `missing_fields`: set of field names

**Outputs**  
- `rag_suggestions`: dict mapping field -> list[str] suggestions  
- (Optionally) short rationales or source snippets for each suggestion

**Model / APIs**
- OpenAI Responses API with `gpt-5-nano` / `gpt-4.1-nano`
- File Search tool driven by `vector_store_id` (no separate API call)

**When**  
- Before FQG (to seed “suggestions” in questions)  
- On-demand enrichment (e.g. to suggest skills, benefits, tech stacks)

---

## 4) Company Info Agent

**Purpose**  
Extract company name, location, mission/values, and culture from a given company website (homepage and `/impressum` or equivalent if present).

**Inputs**  
- `company_url` (string)  
- Page text content (fetched via ingestion utils)

**Outputs**  
- `company_name`  
- `location`  
- `company_mission`  
- `company_culture`

**Model / APIs**
- OpenAI Responses API with `gpt-5-nano` / `gpt-4.1-nano` for structured text extraction
- Uses `ingest.extractors` to fetch website content

**When**
- Company info step (“Fetch from website” action in the UI)

---

## 5) Suggestion Agents (Helpers)

- **Task Suggester** – Propose top responsibilities/tasks for the role
- **Skill Suggester** – Suggest technical and soft skills (with ESCO normalization)
- **Benefit Suggester** – Suggest common perks/benefits using internal lists and LLM guesses
- **Boolean Builder** – Compose a candidate search string from title + skills (Boolean Builder 2.0)
- **Interview Guide Generator** – Generate interview questions & scoring rubrics
- **Job‑Ad Writer** – Draft a polished, SEO-aware job ad in Markdown format

**Models**
- OpenAI Responses API with `gpt-5-nano` / `gpt-4.1-nano`

---

## 6) Auto Re‑ask Loop

**Purpose**
Automatically invoke the FQG until all critical fields are answered, reducing manual clicks.

**Inputs**
- Current vacancy JSON (`profile`)
- `lang`
- Optional `vector_store_id` (passed through to FQG)

**Outputs**
- Updated follow-up questions (same schema as FQG)

**Model / APIs**
- Delegates to FQG, thus OpenAI Responses API with `gpt-5-nano` / `gpt-4.1-nano` and optional File Search tool

**When**
- After extraction when the user enables **Auto Follow-ups**; implemented in `_extract_and_summarize`

---

## 7) Planned Agents

*(Planned enhancements and future autonomous agents)*

- **Tech‑Stack Miner** – Identify prevalent tech stack elements for the role/industry via RAG + ESCO patterns
- **Compliance Checker** – Check outputs for bias, EEO/GDPR compliance, add boilerplate as needed
- **DEI Language Auditor** – Provide inclusive language suggestions (flag potentially discriminatory phrasing)
- **Content Cost Router** – Auto-select between `gpt-5-nano`, `gpt-4.1-nano`, or `gpt-3.5-turbo` based on content complexity to manage cost
