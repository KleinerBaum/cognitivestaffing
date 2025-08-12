# Vacalyser — Autonomous Agents

This doc lists all current and planned autonomous agents in Vacalyser. Each agent is small, focused, and composable.

---

## 1) Follow‑Up Question Generator (FQG)

**Purpose**  
Turn partially filled vacancy JSON into a minimal, targeted list of questions that closes all gaps with the fewest user interactions.

**Inputs**  
- `extracted`: dict (current vacancy JSON)  
- `lang`: "en" | "de"  
- ESCO context (occupation, essential skills)  
- RAG suggestions (per field, optional)

**Outputs**  
- `questions`: list of objects  
  - `field`: schema key (or "")
  - `question`: localized string
  - `priority`: "critical" | "normal" | "optional"
  - `suggestions`: list[str] (optional; to render as chips)

**Model / APIs**  
- OpenAI GPT‑4o / 4o‑mini (Responses or Chat)  
- ESCO (occupation + essential skills)  
- OpenAI File Search (vector store RAG)

**When**  
- After initial extraction  
- After each user update (optional re‑ask)

---

## 2) ESCO Enricher

**Purpose**  
Normalize role context and surface **missing essential skills** by ESCO; standardize skill labels.

**Inputs**  
- `job_title`, `lang`  
- existing lists (requirements/responsibilities/tools)

**Outputs**  
- `occupation`: {preferredLabel, group, uri}  
- `essential_skills`: list[str]  
- `missing_esco_skills`: list[str]  
- normalized labels for suggested skills

**Model / APIs**  
- ESCO REST: occupation match + skill relations

**When**  
- During extraction & FQG  
- When suggesting skills/tasks

---

## 3) RAG Completion Agent

**Purpose**
Fill or propose values for missing fields using your **OpenAI vector store** (set via the `VECTOR_STORE_ID` env var; omit to disable).

**Inputs**  
- job context (title + industry + current JSON)  
- `missing_fields` set

**Outputs**  
- `rag_suggestions`: dict[field] -> list[str]
- (optionally) short rationales or source snippets

**Model / APIs**  
- OpenAI Responses + File Search (`vector_store_ids=[…]`)

**When**  
- Before FQG (to seed “suggestions”)  
- On-demand enrichment (skills/benefits/tech stacks)

---

## 4) Company Info Agent

**Purpose**  
Extract company name, location, mission/values, culture from a given website (home + /impressum if present).

**Inputs**  
- `company_url`  
- page text (via ingestion utils)

**Outputs**  
- `company_name`, `location`, `company_mission`, `company_culture`

**Model / APIs**  
- OpenAI GPT‑4o / 4o‑mini for structured extraction

**When**  
- Company info step (“Fetch from website”)

---

## 5) Suggestion Agents (Helpers)

- **Task Suggester**: propose top responsibilities for a role  
- **Skill Suggester**: propose technical + soft skills; ESCO‑normalize  
- **Benefit Suggester**: propose perks by role/industry  
- **Boolean Builder**: compose sourcing string from title + skills  
- **Interview Guide**: generate Qs + scoring rubrics  
- **Job‑Ad Writer**: craft SEO‑aware job ad in Markdown

**Models**  
- GPT‑4o / 4o‑mini

---

## 6) Planned Agents

- **Tech‑Stack Miner** (industry + role patterns via RAG/ESCO)  
- **Compliance Checker** (bias/EEO/GDPR boilerplate check)  
- **DEI Language Auditor** (inclusive language hints)  
- **Content Cost Router** (auto choose 4o‑mini vs 4o vs 3.5)  
- **Automatic Re‑ask Loop** (close remaining gaps without UI clicks)

---
