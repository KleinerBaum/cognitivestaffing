# Vacalyser — AI Recruitment Need Analysis (Streamlit)

**Vacalyser** turns messy job ads into a **complete, structured vacancy profile**, then asks only the *minimal* follow‑ups. It enriches with **ESCO** (skills/occupations) and your **OpenAI Vector Store** to propose **missing skills, benefits, tools, and tasks**. Finally, it generates a polished **job ad**, **interview guide**, and **boolean search string**.

## Highlights
- **Dynamic Wizard**: multi‑step, bilingual (EN/DE), low‑friction inputs
- **One‑hop extraction**: Parse PDFs/DOCX/URLs into 20+ fields
- **Structured output**: function calling/JSON mode ensures valid responses
- **API helper**: `call_chat_api` supports OpenAI function calls for reliable extraction
- **Smart follow‑ups**: priority-based questions enriched with ESCO & RAG that dynamically cap the number of questions by field importance, shown inline in relevant steps. Critical questions are highlighted with a red asterisk.
- **ESCO‑Power**: occupation classification + essential skill gaps
- **RAG‑Assist**: use your vector store to fill/contextualize
- **No system OCR deps**: uses **OpenAI Vision** (set `OCR_BACKEND=none` to disable)
- **Cost‑aware**: hybrid models (4o‑mini default), minimal re‑asks
- **Model toggle**: choose GPT‑3.5 (fast, cheap) or GPT‑4 (accurate) for suggestions
- **Robust error handling**: user-facing alerts for API or network issues
- **Cross-field deduplication**: avoids repeating the same information across multiple fields
- **Categorized summary**: groups related fields under clear headings for faster review
- **Missing info alerts**: highlights empty critical fields in the summary and lets you jump back to fill them
- **Boolean Builder 2.0**: interactive search string with selectable skills and title synonyms
- **Export**: clean JSON profile, job‑ad markdown, interview guide
- **Customizable interview guides**: choose 3–10 questions
- **Comprehensive job ads**: generated ads now mention requirements, salary and work policy when provided
- **Onboarding Intro**: welcome step explains required inputs and allows skipping for returning users

---

## Quick Start

```bash
git clone https://github.com/KleinerBaum/cognitivestaffing
cd cognitivestaffing
pip install -r requirements.txt  # or: pip install -e .
streamlit run app.py
```

### Optional: RAG vector store

To enable retrieval-augmented suggestions, create an OpenAI vector store and
set the environment variable `VECTOR_STORE_ID` to its ID:

```bash
export VECTOR_STORE_ID=vs_XXXXXXXXXXXXXXXXXXXXXXXX
```

If `VECTOR_STORE_ID` is unset or empty, Vacalyser runs without RAG.
