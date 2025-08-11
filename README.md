
# Vacalyser — AI Recruitment Need Analysis (Streamlit)

**Vacalyser** turns messy job ads into a **complete, structured vacancy profile**, then asks only the *minimal* follow‑ups. It enriches with **ESCO** (skills/occupations) and your **OpenAI Vector Store** to propose **missing skills, benefits, tools, and tasks**. Finally, it generates a polished **job ad**, **interview guide**, and **boolean search string**.

## Highlights
- **Dynamic Wizard**: multi‑step, bilingual (EN/DE), low‑friction inputs
- **One‑hop extraction**: Parse PDFs/DOCX/URLs into 20+ fields
- **ESCO‑Power**: occupation classification + essential skill gaps
- **RAG‑Assist**: use your vector store to fill/contextualize
- **No system OCR deps**: choose **OpenAI Vision** / **AWS Textract** / **RapidOCR** (pip‑only)
- **Cost‑aware**: hybrid models (4o‑mini default), minimal re‑asks
- **Export**: clean JSON profile, job‑ad markdown, interview guide

---

## Quick Start

```bash
git clone https://github.com/KleinerBaum/cognitivestaffing
cd cognitivestaffing
pip install -r requirements.txt  # or: pip install -e .
streamlit run app.py
```

## Configuration

- `OPENAI_MODEL`: default model used for general calls (e.g. `gpt-4o-mini`).
- `LLM_MODE`: extraction mode (`plain`, `json`, or `function`).
- `USE_RAG`: set to `0` to disable vector-store suggestions.
- `OCR_BACKEND`: choose OCR provider (`tesseract`, `openai`, `textract`, `rapidocr`).
