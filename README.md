# Vacalyser — AI-Powered Recruitment Need Analysis

A modern Streamlit Cloud app that parses job ads, autofills key fields, and asks only the minimum follow-ups to complete a vacancy profile. Generates SEO-ready job ads, Boolean search strings, and interview guides. Styled with Tailwind (CDN) via a tiny component.

## Features
- PDF/DOCX/TXT/URL ingestion
- ESCO skill enrichment (preferred labels)
- OpenAI prompts for extraction, suggestions, and content generation
- Dynamic, low-friction wizard (EN/DE)
- Simple auth (bcrypt hashes in Streamlit secrets)
- Usage logging per user

## Setup
```bash
pip install -r requirements.txt
streamlit run app.py
