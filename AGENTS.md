# Vacalyser — Autonomous Agents

This document lists all current and planned autonomous agents in Vacalyser, along with their roles and interfaces. Each agent is small, focused, and composable. *Note: “GPT‑4o” and “GPT‑4o‑mini” refer to internal cost-optimized variants of OpenAI’s GPT-4 model used in this project.*

---

## Configuration

All agents depend on OpenAI credentials provided via environment variables or
`st.secrets["openai"]`:

- `OPENAI_API_KEY` – required API key for all LLM calls.
- `OPENAI_BASE_URL` – optional custom endpoint (e.g., Azure or Responses API).
- `OPENAI_MODEL` – optional default model override.
- `VECTOR_STORE_ID` – required for the RAG Completion Agent to query an OpenAI
  vector store via File Search.
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
- OpenAI GPT‑4o / 4o‑mini (OpenAI Chat Completion API)  
- ESCO API (occupation + essential skills lookup)  
- OpenAI File Search (Vector Store RAG for context)

**When**  
- After initial extraction  
- After each user update (optional re‑ask triggered)

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
Fill or propose values for missing fields using your **OpenAI vector store** (set via the `VECTOR_STORE_ID` env var; omit or leave empty to disable).

**Inputs**  
- Job context (title, industry, current JSON)  
- `missing_fields`: set of field names

**Outputs**  
- `rag_suggestions`: dict mapping field -> list[str] suggestions  
- (Optionally) short rationales or source snippets for each suggestion

**Model / APIs**  
- OpenAI GPT‑4o / 4o‑mini (for completion)  
- OpenAI File Search API (`vector_store_id=[…]` for retrieval)

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
- OpenAI GPT‑4o / 4o‑mini for structured text extraction

**When**  
- Company info step (“Fetch from website” action in the UI)

---

## 5) Suggestion Agents (Helpers)

- **Task Suggester** – Propose top responsibilities/tasks for the role  
- **Skill Suggester** – Suggest technical and soft skills (with ESCO normalization)  
- **Benefit Suggester** – Suggest common perks/benefits given the role/industry  
- **Boolean Builder** – Compose a candidate search string from title + skills  
- **Interview Guide Generator** – Generate interview questions & scoring rubrics  
- **Job‑Ad Writer** – Draft a polished, SEO-aware job ad in Markdown format

**Models**  
- OpenAI GPT‑4o / 4o‑mini (for all suggestion generators)

---

## 6) Planned Agents

*(Planned enhancements and future autonomous agents)*

- **Tech‑Stack Miner** – Identify prevalent tech stack elements for the role/industry via RAG + ESCO patterns  
- **Compliance Checker** – Check outputs for bias, EEO/GDPR compliance, add boilerplate as needed  
- **DEI Language Auditor** – Provide inclusive language suggestions (flag potentially discriminatory phrasing)  
- **Content Cost Router** – Auto-select between GPT‑4o, 4o‑mini, or GPT-3.5 based on content complexity to manage cost  
- **Automatic Re‑ask Loop** – Automate iterative questioning to close remaining field gaps without user clicks (continuously ask follow-ups until all critical fields are filled)
