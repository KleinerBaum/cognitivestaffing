import os
import fitz  # PyMuPDF
from io import BytesIO
import re

def extract_text_from_file(file_bytes: bytes, file_name: str) -> str:
    if not file_bytes:
        return ""
    file_name = file_name.lower()
    text = ""
    try:
        if file_name.endswith(".pdf"):
            with fitz.open(stream=file_bytes, filetype="pdf") as doc:
                for page in doc:
                    text += page.get_text()
        elif file_name.endswith(".docx") or file_name.endswith(".doc"):
            import docx
            doc = docx.Document(BytesIO(file_bytes))
            full_text = [para.text for para in doc.paragraphs]
            text = "\n".join(full_text)
        else:
            text = file_bytes.decode("utf-8", errors="ignore")
    except Exception:
        text = ""
    return text.strip()

def highlight_keywords(text: str, keywords: list[str]) -> str:
    if not text or not keywords:
        return text
    pattern = re.compile("|".join([re.escape(k) for k in keywords]), re.IGNORECASE)
    return pattern.sub(lambda m: f"**{m.group(0)}**", text)

def build_boolean_query(job_title: str, skills: list[str]) -> str:
    job_title_part = f"\"{job_title}\"" if job_title else ""
    skill_terms = [f"\"{s.strip()}\"" for s in skills if s.strip()]
    if job_title_part and skill_terms:
        skills_query = " OR ".join(skill_terms)
        return f'{job_title_part} AND ({skills_query})'
    elif job_title_part:
        return job_title_part
    else:
        return " OR ".join(skill_terms)

def seo_optimize(text: str, max_keywords: int = 5) -> dict:
    result = {"keywords": [], "meta_description": ""}
    if not text:
        return result
    words = re.findall(r"\b[a-zA-Z]{4,}\b", text.lower())
    freq = {}
    for w in words:
        freq[w] = freq.get(w, 0) + 1
    top_words = sorted(freq, key=freq.get, reverse=True)
    result["keywords"] = [w for w in top_words[:max_keywords]]
    first_sentence_end = re.search(r'[.!?]', text)
    if first_sentence_end:
        first_sentence = text[:first_sentence_end.end()]
    else:
        first_sentence = text[:160]
    if len(first_sentence) > 160:
        first_sentence = first_sentence[:157] + "..."
    result["meta_description"] = first_sentence.strip()
    return result

def ensure_logs_dir():
    try:
        os.makedirs("logs", exist_ok=True)
    except Exception:
        pass
