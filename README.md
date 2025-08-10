# Vacalyser — AI-Powered Recruitment Need Analysis

A modern Streamlit Cloud app that parses job ads, autofills key fields, and now adapts its follow-up questions to gather a complete vacancy profile. Generates SEO-ready job ads, Boolean search strings, and interview guides. Styled with Tailwind (CDN) via a tiny component.

## Features
- Robust PDF/DOCX/TXT/URL ingestion with OCR for scanned PDFs
- ESCO skill enrichment (preferred labels)
- Essential skill checks via ESCO to flag missing requirements
- OpenAI prompts for extraction, suggestions, and content generation
- Dynamic, low-friction wizard (EN/DE)
- Adaptive follow-up questioning for comprehensive vacancy data

## Setup
```bash
pip install -r requirements.txt
streamlit run app.py
```
