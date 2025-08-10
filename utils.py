import fitz  # PyMuPDF for PDF reading
from io import BytesIO
import re

# Utility: Extract text from an uploaded file (PDF, DOCX, or TXT)
def extract_text_from_file(file_bytes: bytes, file_name: str) -> str:
    """Extract text from PDF, DOCX, or TXT file bytes."""
    if not file_bytes:
        return ""
    file_name = file_name.lower()
    text = ""
    try:
        if file_name.endswith(".pdf"):
            # Use PyMuPDF to extract PDF text
            with fitz.open(stream=file_bytes, filetype="pdf") as doc:
                for page in doc:
                    text += page.get_text()
        elif file_name.endswith(".docx") or file_name.endswith(".doc"):
            # Use python-docx to extract text from Word documents
            import docx
            doc = docx.Document(BytesIO(file_bytes))
            full_text = [para.text for para in doc.paragraphs]
            text = "\n".join(full_text)
        else:
            # Assume plain text
            text = file_bytes.decode("utf-8", errors="ignore")
    except Exception as e:
        text = ""  # If extraction fails, return empty string
    return text.strip()

# Utility: Highlight keywords in a text by wrapping them with ** for Markdown
def highlight_keywords(text: str, keywords: list[str]) -> str:
    if not text or not keywords:
        return text
    pattern = re.compile("|".join([re.escape(k) for k in keywords]), re.IGNORECASE)
    return pattern.sub(lambda m: f"**{m.group(0)}**", text)

# Utility: Build a Boolean search query string from a job title and list of skills
def build_boolean_query(job_title: str, skills: list[str]) -> str:
    """Construct a simple boolean query (for searching resumes or profiles)."""
    job_title_part = f"\"{job_title}\"" if job_title else ""
    skill_terms = [f"\"{s.strip()}\"" for s in skills if s.strip()]
    if job_title_part and skill_terms:
        skills_query = " OR ".join(skill_terms)
        return f'{job_title_part} AND ({skills_query})'
    elif job_title_part:
        return job_title_part
    else:
        return " OR ".join(skill_terms)

# Utility: Basic SEO optimization suggestion (keywords + meta description)
def seo_optimize(text: str, max_keywords: int = 5) -> dict:
    """Suggest simple SEO keywords and a meta description for given text."""
    result = {"keywords": [], "meta_description": ""}
    if not text:
        return result
    # Frequency-based keyword extraction (very simple approach)
    words = re.findall(r"\b[a-zA-Z]{4,}\b", text.lower())
    freq = {}
    for w in words:
        freq[w] = freq.get(w, 0) + 1
    top_words = sorted(freq, key=freq.get, reverse=True)
    result["keywords"] = [w for w in top_words[:max_keywords]]
    # Meta description: first sentence or first 160 chars
    first_sentence_end = re.search(r'[.!?]', text)
    if first_sentence_end:
        first_sentence = text[:first_sentence_end.end()]
    else:
        first_sentence = text[:160]
    if len(first_sentence) > 160:
        first_sentence = first_sentence[:157] + "..."
    result["meta_description"] = first_sentence.strip()
    return result
