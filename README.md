# Vacalyser — AI Recruitment Need Analysis (Streamlit)

**Vacalyser** turns messy job ads into a **complete, structured vacancy profile**, then asks only the *minimal* follow‑ups. It enriches with **ESCO** (skills/occupations) and your **OpenAI Vector Store** to propose **missing skills, benefits, tools, and tasks**. Finally, it generates a polished **job ad**, **interview guide**, and **boolean search string**.

## Highlights
- **Dynamic Wizard**: multi‑step, bilingual (EN/DE), low‑friction inputs
- **One‑hop extraction**: Parse PDFs/DOCX/URLs into 20+ fields
- **Structured output**: function calling/JSON mode ensures valid responses
- **API helper**: `call_chat_api` supports OpenAI function calls for reliable extraction
- **Smart follow‑ups**: priority-based questions enriched with ESCO & RAG that dynamically cap the number of questions by field importance, shown inline in relevant steps
- **ESCO‑Power**: occupation classification + essential skill gaps
- **RAG‑Assist**: use your vector store to fill/contextualize
- **No system OCR deps**: uses **OpenAI Vision** (set `OCR_BACKEND=none` to disable)
- **Cost‑aware**: hybrid models (4o‑mini default), minimal re‑asks
- **Robust error handling**: user-facing alerts for API or network issues
- **Cross-field deduplication**: avoids repeating the same information across multiple fields
- **Boolean Builder 2.0**: interactive search string with selectable skills and title synonyms
- **Export**: clean JSON profile, job‑ad markdown, interview guide
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
