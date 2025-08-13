import json
from pathlib import Path

import streamlit as st
from typing import Any, cast, TypedDict

from core.ss_bridge import from_session_state, to_session_state
from core.schema import coerce_and_fill
from utils import (
    extract_text_from_file,
    extract_text_from_url,
    merge_texts,
    build_boolean_query,
    seo_optimize,
    ensure_logs_dir,
)
from utils.export import prepare_download_data
from openai_utils import (
    call_chat_api,
    suggest_additional_skills,
    suggest_benefits,
    generate_interview_guide,
    generate_job_ad,
    extract_company_info,
    refine_document,
    what_happened,
)
from llm.context import build_extract_messages
from llm.client import build_extraction_function
from question_logic import CRITICAL_FIELDS, generate_followup_questions
from core import esco_utils  # Added import to use ESCO classification
from streamlit_sortables import sort_items
from nlp.bias import scan_bias_language
from components.model_selector import model_selector

MODEL_OPTIONS = {
    "GPT-3.5 (fast, cheap)": "gpt-3.5-turbo",
    "GPT-4 (slow, accurate)": "gpt-4",
}

TONE_CHOICES = {
    "formal": {
        "en": "Formal",
        "de": "Formell",
        "tone_en": "formal and straightforward",
        "tone_de": "formal und direkt",
    },
    "casual": {
        "en": "Casual",
        "de": "Locker",
        "tone_en": "casual and friendly",
        "tone_de": "locker und freundlich",
    },
    "creative": {
        "en": "Creative",
        "de": "Kreativ",
        "tone_en": "creative and lively",
        "tone_de": "kreativ und lebendig",
    },
    "diversity": {
        "en": "Diversity-Focused",
        "de": "Diversitätsbetont",
        "tone_en": "engaging and inclusive",
        "tone_de": "ansprechend und inklusiv",
    },
}

lang = st.session_state.get("lang", "en")


FIELD_SECTION_MAP: dict[str, int] = {
    "position.job_title": 1,
    "company.name": 1,
    "company.industry": 1,
    "company.hq_location": 1,
    "company.size": 1,
    "location.primary_city": 1,
    "location.country": 1,
    "position.role_summary": 2,
    "responsibilities.items": 2,
    "requirements.hard_skills": 3,
    "requirements.soft_skills": 3,
    "requirements.tools_and_technologies": 3,
    "requirements.languages_required": 3,
    "requirements.certifications": 3,
    "employment.job_type": 4,
    "employment.work_policy": 4,
    "compensation.salary_min": 4,
    "compensation.salary_max": 4,
}
"""Map critical field names to wizard section indices for navigation."""


FIELD_LABELS: dict[str, tuple[str, str]] = {
    "position.job_title": ("Job Title", "Stellenbezeichnung"),
    "company.name": ("Company Name", "Unternehmensname"),
    "company.industry": ("Industry", "Branche"),
    "company.hq_location": ("Headquarters Location", "Hauptsitz"),
    "company.size": ("Company Size", "Unternehmensgröße"),
    "location.primary_city": ("City", "Stadt"),
    "location.country": ("Country", "Land"),
    "position.role_summary": ("Role Summary", "Rollenübersicht"),
    "responsibilities.items": ("Responsibilities", "Verantwortlichkeiten"),
    "requirements.hard_skills": ("Hard Skills", "Technische Fähigkeiten"),
    "requirements.soft_skills": ("Soft Skills", "Soziale Fähigkeiten"),
    "requirements.tools_and_technologies": (
        "Tools & Technologies",
        "Tools & Technologien",
    ),
    "requirements.languages_required": (
        "Languages Required",
        "Erforderliche Sprachen",
    ),
    "requirements.certifications": ("Certifications", "Zertifizierungen"),
    "employment.job_type": ("Employment Type", "Anstellungsart"),
    "employment.work_policy": ("Work Policy", "Arbeitsmodell"),
    "compensation.salary_min": ("Salary Minimum", "Mindestgehalt"),
    "compensation.salary_max": ("Salary Maximum", "Höchstgehalt"),
}
"""Human-friendly labels for critical wizard fields."""


def get_field_label(field: str, lang: str) -> str:
    """Return the localized label for a given field name.

    Args:
        field: Internal field identifier.
        lang: Language code, e.g. ``"en"`` or ``"de"``.

    Returns:
        Localized label for ``field``.
    """
    en, de = FIELD_LABELS.get(field, (field, field))
    return en if lang != "de" else de


class SummaryCategory(TypedDict):
    """Structure for grouping summary fields."""

    en: str
    de: str
    fields: list[str]


SUMMARY_CATEGORIES: list[SummaryCategory] = [
    {
        "en": "Company & Context",
        "de": "Unternehmen & Kontext",
        "fields": [
            "company.name",
            "company.website",
            "company.industry",
            "company.hq_location",
            "company.size",
            "location.primary_city",
            "location.country",
            "company.mission",
            "company.culture",
        ],
    },
    {
        "en": "Role Details",
        "de": "Rollenbeschreibung",
        "fields": [
            "position.job_title",
            "position.role_summary",
            "responsibilities.items",
            "position.department",
            "position.team_structure",
            "position.reporting_line",
        ],
    },
    {
        "en": "Requirements",
        "de": "Anforderungen",
        "fields": [
            "requirements.hard_skills",
            "requirements.soft_skills",
            "requirements.tools_and_technologies",
            "requirements.languages_required",
            "requirements.certifications",
            "position.seniority_level",
        ],
    },
    {
        "en": "Benefits & Conditions",
        "de": "Leistungen & Konditionen",
        "fields": [
            "employment.job_type",
            "employment.work_policy",
            "employment.onsite_days_per_week",
            "employment.travel_required",
            "employment.work_hours_per_week",
            "compensation.salary_min",
            "compensation.salary_max",
            "compensation.variable_pay",
            "compensation.benefits",
            "compensation.healthcare_plan",
            "compensation.pension_plan",
            "compensation.equity_offered",
            "employment.relocation_support",
            "employment.visa_sponsorship",
        ],
    },
    {
        "en": "Process",
        "de": "Prozess",
        "fields": [
            "target_start_date",
            "application_deadline",
            "performance_metrics",
            "interview_stages",
            "process_notes",
        ],
    },
]


def normalise_state(reapply_aliases: bool = True):
    """Normalize session state to canonical schema keys and update JSON."""
    jd = from_session_state(cast(dict[str, Any], st.session_state))
    to_session_state(jd, cast(dict[str, Any], st.session_state))
    if reapply_aliases:
        # Keep legacy alias fields in sync for UI (if needed)
        st.session_state["requirements"] = st.session_state.get("qualifications", "")
        st.session_state["tasks"] = st.session_state.get("responsibilities", "")
        st.session_state["contract_type"] = st.session_state.get("job_type", "")
    st.session_state["validated_json"] = json.dumps(
        jd.model_dump(mode="json"), indent=2, ensure_ascii=False
    )
    return jd


def apply_global_styling(theme: str = "dark") -> None:
    """Apply global styling and background image to the app.

    Injects fonts and colors into the Streamlit application. When ``theme`` is
    ``"dark"`` a textured background image and dark palette are used. For
    ``"light"`` the background image is removed and light colors are applied.
    """

    bg_path = Path("images/AdobeStock_506577005.jpeg")
    if theme == "dark":
        st.markdown(
            f"""
            <style>
                .stApp {{
                    background: url("{bg_path.as_posix()}") no-repeat center center fixed;
                    background-size: cover;
                }}
            </style>
            """,
            unsafe_allow_html=True,
        )
        body_styles = "body, .stApp { background-color: #0b0f14; color: #e5e7eb; font-family: 'Comfortaa', sans-serif; }"
        card_bg = "#111827"
        heading_color = "#ffffff"
    else:
        st.markdown(
            """
            <style>
                .stApp { background: none !important; }
            </style>
            """,
            unsafe_allow_html=True,
        )
        body_styles = "body, .stApp { background-color: #ffffff; color: #111827; font-family: 'Comfortaa', sans-serif; }"
        card_bg = "#f9fafb"
        heading_color = "#000000"

    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Comfortaa:wght@300;400;700&display=swap');
        {body_styles}
        h1,h2,h3,h4 {{ color: {heading_color}; }}
        .card {{ background-color: {card_bg}; padding: 1rem; border-radius: 12px; margin-bottom: 1.25rem; }}
        .stButton > button {{ border-radius: 10px; min-height: 2.5rem; }}
        @media (max-width: 768px) {{
            div[data-testid="stHorizontalBlock"] {{ flex-direction: column; }}
            div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {{ width: 100%; }}
            .stButton > button {{ width: 100%; }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _is_blank(value: Any) -> bool:
    """Return ``True`` if a value is empty."""

    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, set)):
        return len(value) == 0
    return False


def get_missing_critical_fields(max_section: int | None = None) -> list[str]:
    """List critical fields that are still empty up to ``max_section``.

    Args:
        max_section: Highest wizard section to inspect. ``None`` checks all
            sections.

    Returns:
        Sorted list of missing field names.
    """

    limit = (
        max_section
        if max_section is not None
        else max(FIELD_SECTION_MAP.values(), default=0)
    )
    missing: set[str] = set()
    for field in CRITICAL_FIELDS:
        section = FIELD_SECTION_MAP.get(field, 0)
        if section <= limit and _is_blank(st.session_state.get(field)):
            missing.add(field)

    followups = st.session_state.get("followup_questions", [])
    for item in followups:
        field = item.get("field")
        if not field or item.get("priority") != "critical":
            continue
        section = FIELD_SECTION_MAP.get(field, limit)
        if section <= limit and _is_blank(st.session_state.get(field)):
            missing.add(field)

    return sorted(missing)


def show_navigation(current_step: int, total_steps: int) -> None:
    """Render Previous/Next navigation buttons for the wizard.

    Prevents advancing while any critical field on current or previous pages
    is left blank. The intro page (step 0) hides navigation controls.
    """

    lang = st.session_state.get("lang", "en")
    if current_step == 0:
        return

    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        if current_step > 0:
            prev_label = "⬅ Previous" if lang != "de" else "⬅ Zurück"
            if st.button(prev_label):
                st.session_state["current_section"] -= 1
                st.rerun()
    with col3:
        if current_step < total_steps - 1:
            next_label = "Next ➡" if lang != "de" else "Weiter ➡"
            if st.button(next_label):
                missing = get_missing_critical_fields(current_step)
                if missing:
                    labels = [get_field_label(f, lang) for f in missing]
                    warn = (
                        "Please fill the required fields before continuing: "
                        if lang != "de"
                        else "Bitte füllen Sie die Pflichtfelder aus, bevor Sie fortfahren: "
                    )
                    st.warning(warn + ", ".join(labels))
                else:
                    st.session_state["current_section"] += 1
                    st.rerun()


def render_followups_for(fields: list[str] | None = None) -> None:
    """Display follow-up questions inline for specified fields.

    Critical questions are prefixed with a red asterisk to signal required
    input.

    Args:
        fields: List of field names relevant to the current page. If ``None``,
            all follow-up questions are considered.
    """
    followups = st.session_state.get("followup_questions", [])
    if not followups:
        return

    allowed = set(fields) if fields else None
    rank = {"critical": 0, "normal": 1, "optional": 2}
    relevant = [
        f
        for f in followups
        if not allowed or f.get("field") in allowed or not f.get("field")
    ]
    if not relevant:
        return

    relevant.sort(key=lambda item: rank.get(item.get("priority", "normal"), 1))

    for item in relevant:
        field = item.get("field", "")
        question = item.get("question", "")
        key = field or question
        is_critical = item.get("priority") == "critical"

        label = ""
        if is_critical:
            st.markdown(
                f"<span style='color:red'>* {question}</span>", unsafe_allow_html=True
            )
        else:
            label = question

        if field:
            default_val = st.session_state.get(field) or item.get("prefill", "")
            st.session_state[field] = st.text_input(label, default_val, key=key)
        else:
            _ = st.text_input(label, "", key=key)

        suggestions = item.get("suggestions") or []
        if suggestions and field:
            cols = st.columns(len(suggestions))
            for idx, (col, sugg) in enumerate(zip(cols, suggestions)):
                with col:
                    if st.button(sugg, key=f"{key}_sugg_{idx}"):
                        existing = st.session_state.get(field, "")
                        sep = "\n" if existing else ""
                        st.session_state[field] = f"{existing}{sep}{sugg}"
                        st.rerun()

    st.session_state["followup_questions"] = [
        f
        for f in followups
        if not f.get("field")
        or not st.session_state.get(f.get("field", ""), "").strip()
    ]


def editable_draggable_list(field: str, label: str) -> None:
    """Render a draggable list for newline-separated session values.

    Args:
        field: Session state key storing newline-separated values.
        label: Display label for the list.
    """
    lang = st.session_state.get("lang", "en")
    raw = st.session_state.get(field, "")
    items = [s.strip() for s in raw.splitlines() if s.strip()]
    # Callbacks are used to safely mutate widget state without triggering
    # ``StreamlitAPIException``. Direct assignment to ``st.session_state`` for
    # an existing widget key is not allowed once the widget is instantiated.

    def _add_item() -> None:
        """Append the value from the input box to the list of items."""
        nonlocal items
        new_item = st.session_state.get(f"{field}_new", "").strip()
        if new_item:
            items.append(new_item)
            st.session_state[f"{field}_new"] = ""

    add_label = f"Add {label}" if lang != "de" else f"{label} hinzufügen"
    st.text_input(add_label, key=f"{field}_new")
    st.button(
        "Add" if lang != "de" else "Hinzufügen", key=f"{field}_add", on_click=_add_item
    )

    def _remove_items() -> None:
        """Remove selected entries from the list and clear the selection."""
        nonlocal items
        selected = st.session_state.get(f"{field}_remove", [])
        if selected:
            items = [i for i in items if i not in selected]
            st.session_state[f"{field}_remove"] = []

    if items:
        remove_label = f"Remove {label}" if lang != "de" else f"{label} entfernen"
        st.multiselect(
            remove_label,
            items,
            key=f"{field}_remove",
            on_change=_remove_items,
        )
        items = sort_items(
            items, header=label, direction="vertical", key=f"{field}_sort"
        )

    st.session_state[field] = "\n".join(items)


def render_summary_input(field: str, label: str, highlight_missing: bool) -> None:
    """Render an editable input for the summary page.

    Uses a text area for multiline content and a text input for shorter values.

    Args:
        field: Session state key to render.
        label: Display label for the field.
        highlight_missing: Whether the field is required but empty.
    """
    value = st.session_state.get(field, "")
    widget = (
        st.text_area if ("\n" in str(value) or len(str(value)) > 80) else st.text_input
    )
    widget_label = f"❗ {label}" if highlight_missing else label
    widget(widget_label, value, key=field)


def intro_page() -> None:
    """Display an introductory page explaining the wizard flow."""
    lang = st.session_state.get("lang", "en")
    if lang == "de":
        st.title("Erkennen Sie Ihre Recruiting-Bedürfnisse")
        st.write(
            "Vermeiden Sie kostspielige Informationsverluste im ersten Schritt jedes Recruiting-Prozesses, sammeln Sie alle unausgesprochenen Informationen für eine spezifische Vakanz, entdecken Sie verborgene Potenziale und nutzen Sie diese auf vielfältige Weise, um nicht nur Geld und Zeit zu sparen, sondern auch das Frustrationsniveau aller Beteiligten zu senken und nachhaltigen Recruiting-Erfolg sicherzustellen."
        )
        st.subheader("Sie benötigen")
        st.markdown("- Stellenanzeige (URL oder PDF)")
        st.markdown("- Kenntnisse über Unternehmensdetails")
        st.write(
            "Der Prozess passt sich dynamisch an die von Ihnen bereitgestellten Informationen an und gestaltet die Datenerhebung individuell für Ihre spezifische Vakanz."
        )
        st.checkbox("Intro beim nächsten Mal überspringen", key="skip_intro")
        if st.button("🚀 Analyse starten"):
            st.session_state["current_section"] = 1
            st.rerun()
    else:
        st.title("Detect Your Recruitment Needs")
        st.write(
            "Avoid expensive Information Loss on the 1st Step of every Recruitment-Process, collect all unspoken information for a specific vacancy, detect hidden potentials and use it in various ways in order to not only save money, but also time, reduce the level of frustration of all involved parties and ensure sustainable recruitment-success"
        )
        st.subheader("You'll need")
        st.markdown("- Job description (URL or PDF)")
        st.markdown("- Knowledge of company details")
        st.write(
            "The Process is designed to dynamically adjust to the information you provide and tailor the gathering process to your specific Vacancy."
        )
        st.checkbox("Skip intro next time", key="skip_intro")
        if st.button("🚀 Start Discovery"):
            st.session_state["current_section"] = 1
            st.rerun()


def _run_extraction(lang: str) -> None:
    """Run vacancy extraction based on current session inputs."""

    url_text = ""
    if st.session_state.get("input_url"):
        url_text = extract_text_from_url(st.session_state["input_url"])
        if not url_text:
            warn = (
                "⚠️ Unable to fetch or parse content from the provided URL."
                if lang != "de"
                else "⚠️ Die bereitgestellte URL konnte nicht abgerufen oder verarbeitet werden."
            )
            st.warning(warn)
    file_text = st.session_state.get("uploaded_text", "")
    combined_text = merge_texts(url_text, file_text)
    if st.session_state.get("job_title") and not combined_text:
        combined_text = st.session_state["job_title"]

    if not combined_text:
        warn = (
            "⚠️ No text available to analyze. Please provide a job ad URL or upload a document."
            if lang != "de"
            else "⚠️ Kein Text zur Analyse verfügbar. Bitte geben Sie eine Stellenanzeigen-URL an oder laden Sie ein Dokument hoch."
        )
        st.warning(warn)
        return

    messages = build_extract_messages(combined_text)
    fn_schema = build_extraction_function()
    try:
        response = call_chat_api(
            messages,
            model=st.session_state.get("llm_model"),
            temperature=0.0,
            functions=[fn_schema],
            function_call={"name": fn_schema["name"]},
        )
    except Exception:  # pragma: no cover - network failure
        st.session_state["extraction_success"] = False
        err_msg = (
            "❌ OpenAI request failed. Please try again later."
            if lang != "de"
            else "❌ OpenAI-Anfrage fehlgeschlagen. Bitte später erneut versuchen."
        )
        st.error(err_msg)
        return
    try:
        data = coerce_and_fill(json.loads(response)).model_dump(mode="json")
        for key, val in data.items():
            st.session_state[key] = (
                "\n".join(val) if isinstance(val, list) else str(val)
            )
        normalise_state()
        try:
            followups = generate_followup_questions(
                cast(dict[str, Any], st.session_state),
                lang=lang,
                use_rag=st.session_state.get("use_rag", True),
            )
        except Exception:  # pragma: no cover - network failure
            warn_msg = (
                "⚠️ Unable to generate follow-up questions."
                if lang != "de"
                else "⚠️ Folgefragen konnten nicht erstellt werden."
            )
            st.warning(warn_msg)
            followups = []
        st.session_state["followup_questions"] = followups
        occ = esco_utils.classify_occupation(
            st.session_state.get("job_title", ""), lang=lang
        )
        if occ:
            st.session_state["occupation_label"] = occ.get("preferredLabel") or occ.get(
                "occupation_label", ""
            )
            st.session_state["occupation_group"] = occ.get("group", "")
        st.session_state["extraction_success"] = True
        log_event(
            f"ANALYZE by {st.session_state.get('user', 'anonymous')} title='{st.session_state.get('job_title', '')}'"
        )
    except Exception:
        st.session_state["extraction_success"] = False
        st.error(
            "❌ Could not parse AI response as JSON. Please try again or rephrase the input."
        )


def render_extraction_summary(lang: str) -> None:
    """Display extracted fields in a tabbed table."""

    tab_labels = [
        cat["de"] if lang == "de" else cat["en"] for cat in SUMMARY_CATEGORIES
    ]
    tabs = st.tabs(tab_labels)
    for tab, category in zip(tabs, SUMMARY_CATEGORIES):
        with tab:
            rows = [
                {
                    ("Field" if lang != "de" else "Feld"): field.replace(
                        "_", " "
                    ).title(),
                    ("Value" if lang != "de" else "Wert"): st.session_state.get(
                        field, ""
                    ),
                }
                for field in category["fields"]
                if st.session_state.get(field)
            ]
            if rows:
                st.table(rows)
            else:
                st.write(
                    "No data extracted." if lang != "de" else "Keine Daten extrahiert."
                )


def start_discovery_page():
    """Start page: Input job title and job ad content (URL or file) for analysis."""
    lang = st.session_state.get("lang", "en")
    st.header(
        "🔍 Start Your Analysis with Vacalyzer"
        if lang != "de"
        else "🔍 Starten Sie Ihre Analyse mit Vacalyzer"
    )
    if st.session_state.get("extraction_complete"):
        st.success(
            "✅ Key information extracted successfully!"
            if lang != "de"
            else "✅ Wichtige Informationen erfolgreich extrahiert!"
        )
        render_extraction_summary(lang)
        label = "Start Discovery" if lang != "de" else "Analyse starten"
        if st.button(f"🚀 {label}"):
            st.session_state["current_section"] = 2
            st.rerun()
        return

    st.caption(
        "Upload a job ad or paste a URL. We’ll extract everything we can — then ask only what’s missing."
        if lang != "de"
        else "Laden Sie eine Stellenanzeige hoch oder fügen Sie eine URL ein. Wir extrahieren alle verfügbaren Informationen und fragen nur fehlende Details ab."
    )
    colA, colB = st.columns(2)
    with colA:
        job_title = st.text_input(
            "Job Title" if lang != "de" else "Stellenbezeichnung",
            st.session_state.get("job_title", ""),
        )
        if job_title:
            st.session_state["job_title"] = job_title
        input_url = st.text_input(
            (
                "Job Ad URL (optional)"
                if lang != "de"
                else "Stellenanzeigen-URL (optional)"
            ),
            st.session_state.get("input_url", ""),
        )
        if input_url:
            st.session_state["input_url"] = input_url
    with colB:
        uploaded_file = st.file_uploader(
            (
                "Upload Job Ad (PDF, DOCX, TXT)"
                if lang != "de"
                else "Stellenanzeige hochladen (PDF, DOCX, TXT)"
            ),
            type=["pdf", "docx", "txt"],
        )
        if uploaded_file is not None:
            file_bytes = uploaded_file.read()
            text = extract_text_from_file(file_bytes, uploaded_file.name)
            if text:
                st.session_state["uploaded_text"] = text
                st.success(
                    "✅ File uploaded and text extracted."
                    if lang != "de"
                    else "✅ Datei hochgeladen und Text extrahiert."
                )
            else:
                st.error(
                    "❌ Failed to extract text from the file."
                    if lang != "de"
                    else "❌ Text konnte nicht aus der Datei extrahiert werden."
                )

    current_source = (
        st.session_state.get("input_url", ""),
        st.session_state.get("uploaded_text", ""),
    )
    if (
        st.session_state.get("input_url") or st.session_state.get("uploaded_text")
    ) and st.session_state.get("last_source") != current_source:
        st.session_state["last_source"] = current_source
        with st.spinner(
            "Analyzing the job ad with AI..."
            if lang != "de"
            else "Stellenanzeige wird mit KI analysiert..."
        ):
            _run_extraction(lang)
        if st.session_state.get("extraction_success"):
            st.session_state["extraction_complete"] = True
            st.rerun()


def company_information_page():
    """Company Info page: Gather basic company information and optionally auto-fetch details from website."""
    lang = st.session_state.get("lang", "en")
    st.header("🏢 Company Information" if lang != "de" else "🏢 Firmeninformationen")
    try:
        st.session_state["followup_questions"] = [
            f
            for f in generate_followup_questions(
                cast(dict[str, Any], st.session_state),
                lang=lang,
                use_rag=st.session_state.get("use_rag", True),
            )
            if f.get("field") not in {"company.mission", "company.culture"}
        ]
    except Exception:  # pragma: no cover - network failure
        pass
    render_followups_for(
        [
            "company.name",
            "company.industry",
            "company.hq_location",
            "company.size",
            "location.primary_city",
            "location.country",
            "company.website",
        ]
    )


st.session_state["company.name"] = st.text_input(
    "Company Name" if lang != "de" else "Unternehmensname",
    st.session_state.get("company.name", ""),
)
industry_options = [
    "Information Technology",
    "Finance",
    "Healthcare",
    "Manufacturing",
    "Retail",
    "Logistics",
    "Automotive",
    "Aerospace",
    "Telecommunications",
    "Energy",
    "Pharmaceuticals",
    "Education",
    "Public Sector",
    "Consulting",
    "Media & Entertainment",
    "Hospitality",
    "Construction",
    "Real Estate",
    "Agriculture",
    "Nonprofit",
    "Insurance",
    "Legal",
    "Biotech",
    "Chemicals",
    "Utilities",
    "Gaming",
    "E-commerce",
    "Cybersecurity",
    "Marketing/Advertising",
]
current_industry = st.session_state.get("company.industry", "")
st.session_state["company.industry"] = st.selectbox(
    "Industry" if lang != "de" else "Branche",
    industry_options,
    index=(
        industry_options.index(current_industry)
        if current_industry in industry_options
        else 0
    ),
    key="company.industry",
)
st.session_state["company.hq_location"] = st.text_input(
    "Headquarters Location" if lang != "de" else "Hauptsitz",
    st.session_state.get("company.hq_location", ""),
)
size_options = [
    "1-10",
    "11-50",
    "51-200",
    "201-1000",
    "1001-5000",
    "5001+",
]
st.session_state["company.size"] = st.selectbox(
    "Company Size" if lang != "de" else "Unternehmensgröße",
    size_options,
    index=(
        size_options.index(st.session_state["company.size"])
        if st.session_state.get("company.size") in size_options
        else 0
    ),
    key="company.size",
)
st.session_state["location.primary_city"] = st.text_input(
    "City" if lang != "de" else "Stadt",
    st.session_state.get("location.primary_city", ""),
)
st.session_state["location.country"] = st.text_input(
    "Country" if lang != "de" else "Land", st.session_state.get("location.country", "")
)
st.session_state["company.website"] = st.text_input(
    "Company Website" if lang != "de" else "Webseite",
    st.session_state.get("company.website", ""),
)
# Optional: Fetch company info (mission, values, etc.) from website
fetch_label = (
    "🔄 Fetch Company Info from Website"
    if lang != "de"
    else "🔄 Unternehmensinfos von der Website abrufen"
)
if st.button(fetch_label):
    with st.spinner(
        "Fetching company information..."
        if lang != "de"
        else "Unternehmensinformationen werden abgerufen..."
    ):
        website = st.session_state.get("company.website", "").strip()
        # Use OpenAI to extract company mission & culture from site (if implemented)
        try:
            info = extract_company_info(website)
        except Exception:
            info = {}
        if info.get("company_mission"):
            st.session_state["company.mission"] = info["company_mission"]
        if info.get("company_culture"):
            st.session_state["company.culture"] = info["company_culture"]


def role_description_page():
    """Role Description page: Summary of the role and key responsibilities."""
    lang = st.session_state.get("lang", "en")
    st.header("📋 Role Description" if lang != "de" else "📋 Rollenbeschreibung")
    try:
        st.session_state["followup_questions"] = generate_followup_questions(
            cast(dict[str, Any], st.session_state),
            lang=lang,
            use_rag=st.session_state.get("use_rag", True),
        )
    except Exception:  # pragma: no cover - network failure
        pass
    render_followups_for(["position.role_summary", "responsibilities.items"])


# Role Details inputs (Section 2)
st.session_state["position.job_title"] = st.text_input(
    "Job Title" if lang != "de" else "Stellenbezeichnung",
    st.session_state.get("position.job_title", ""),
)
# ... (other inputs like department, etc.)
st.session_state["position.role_summary"] = st.text_area(
    "Role Summary / Objective" if lang != "de" else "Rollenübersicht / Ziel",
    st.session_state.get("position.role_summary", ""),
    height=100,
)
responsibilities_label = (
    "Key Responsibilities" if lang != "de" else "Hauptverantwortlichkeiten"
)
editable_draggable_list("responsibilities.items", responsibilities_label)


def task_scope_page():
    """Tasks page: Scope of tasks or projects for the role."""
    lang = st.session_state.get("lang", "en")
    st.header(
        "🗒️ Project/Task Scope" if lang != "de" else "🗒️ Projekt- / Aufgabenbereich"
    )
    render_followups_for(["responsibilities.items"])
    st.session_state["responsibilities.items"] = st.text_area(
        (
            "Main Tasks or Projects"
            if lang != "de"
            else "Wichtigste Aufgaben oder Projekte"
        ),
        st.session_state.get("responsibilities.items", ""),
        height=120,
    )


def skills_competencies_page():
    """Skills page: capture technical, language, and certification requirements."""
    lang = st.session_state.get("lang", "en")
    st.header(
        "🛠️ Required Skills & Competencies"
        if lang != "de"
        else "🛠️ Erforderliche Fähigkeiten & Kompetenzen"
    )
    render_followups_for(
        [
            "requirements.hard_skills",
            "requirements.soft_skills",
            "requirements.tools_and_technologies",
            "requirements.languages_required",
            "requirements.certifications",
        ]
    )
    if not st.session_state.get("hard_skills") and st.session_state.get("requirements"):
        st.session_state["hard_skills"] = st.session_state.get("requirements", "")

    # Requirements inputs (Section 3 - Skills & Competencies)


tech_col, soft_col = st.columns(2)
with tech_col:
    st.subheader("Technical" if lang != "de" else "Technisch")
    editable_draggable_list(
        "requirements.hard_skills",
        "Hard/Technical Skills" if lang != "de" else "Fachliche (Hard) Skills",
    )
    editable_draggable_list(
        "requirements.tools_and_technologies",
        "Tools & Technologies" if lang != "de" else "Tools und Technologien",
    )
    editable_draggable_list(
        "requirements.certifications",
        "Certifications" if lang != "de" else "Zertifizierungen",
    )
with soft_col:
    st.subheader("Soft & Language" if lang != "de" else "Soziale & Sprache")
    editable_draggable_list(
        "requirements.soft_skills", "Soft Skills" if lang != "de" else "Soft Skills"
    )
    editable_draggable_list(
        "requirements.languages_required",
        "Languages Required" if lang != "de" else "Erforderliche Sprachen",
    )

    hard_skills_text = st.session_state.get("hard_skills", "")
    soft_skills_text = st.session_state.get("soft_skills", "")
    tools_text = st.session_state.get("tools_and_technologies", "")
    skill_btn_col, skill_model_col = st.columns([3, 2])
    with skill_model_col:
        skill_model_label = st.selectbox(
            "Model",
            list(MODEL_OPTIONS.keys()),
            key="skill_model",
        )
    with skill_btn_col:
        suggest_label = (
            "💡 Suggest Additional Skills"
            if lang != "de"
            else "💡 Zusätzliche Skills vorschlagen"
        )
        if st.button(suggest_label):
            model_name = MODEL_OPTIONS[skill_model_label]
            # Use AI to suggest additional technical and soft skills
            with st.spinner(
                (
                    f"Generating skill suggestions with {skill_model_label}..."
                    if lang != "de"
                    else f"Skill-Vorschläge werden mit {skill_model_label} generiert..."
                )
            ):
                title = st.session_state.get("job_title", "")
                tasks = st.session_state.get("tasks", "") or st.session_state.get(
                    "responsibilities", ""
                )
                existing_skills: list[str] = []
                for text in (hard_skills_text, soft_skills_text, tools_text):
                    if text:
                        existing_skills.extend(
                            s.strip() for s in text.splitlines() if s.strip()
                        )
                try:
                    suggestions = suggest_additional_skills(
                        job_title=title,
                        responsibilities=tasks,
                        existing_skills=existing_skills,
                        num_suggestions=10,
                        lang="de" if lang == "de" else "en",
                        model=model_name,
                    )
                except Exception:  # pragma: no cover - network failure
                    warn = (
                        "⚠️ Could not generate skill suggestions."
                        if lang != "de"
                        else "⚠️ Konnte keine Skill-Vorschläge generieren."
                    )
                    st.warning(warn)
                    suggestions = {"technical": [], "soft": []}
                tech_suggestions = suggestions.get("technical", [])
                soft_suggestions = suggestions.get("soft", [])
                # Store suggestions in session state to display as chips
                st.session_state["suggested_tech_skills"] = tech_suggestions
                st.session_state["suggested_soft_skills"] = soft_suggestions
        # Notify user to pick from suggestions
        if st.session_state.get("suggested_tech_skills") or st.session_state.get(
            "suggested_soft_skills"
        ):
            st.success(
                (
                    "✔️ Skill suggestions generated. Click on a suggestion to add it."
                    if lang != "de"
                    else "✔️ Skill-Vorschläge generiert. Klicken Sie auf einen Vorschlag, um ihn hinzuzufügen."
                )
            )
    # If suggestions are available, display them as chips for selection
    tech_list = st.session_state.get("suggested_tech_skills", [])
    soft_list = st.session_state.get("suggested_soft_skills", [])
    if tech_list:
        st.caption(
            "**Suggested Technical Skills:**"
            if lang != "de"
            else "**Vorgeschlagene technische Fähigkeiten:**"
        )
        cols = st.columns(len(tech_list))
        for i, (col, skill) in enumerate(zip(cols, tech_list)):
            with col:
                if st.button(skill, key=f"tech_sugg_{i}"):
                    # Append to hard skills
                    current = st.session_state.get("hard_skills", "")
                    sep = "\n" if current else ""
                    if skill not in current:
                        st.session_state["hard_skills"] = f"{current}{sep}{skill}"
                    # Remove the added skill from suggestions
                    st.session_state["suggested_tech_skills"] = [
                        s for s in tech_list if s != skill
                    ]
                    st.rerun()
    if soft_list:
        st.caption(
            "**Suggested Soft Skills:**"
            if lang != "de"
            else "**Vorgeschlagene Soft Skills:**"
        )
        cols = st.columns(len(soft_list))
        for j, (col, skill) in enumerate(zip(cols, soft_list)):
            with col:
                if st.button(skill, key=f"soft_sugg_{j}"):
                    # Append to soft skills
                    current = st.session_state.get("soft_skills", "")
                    sep = "\n" if current else ""
                    if skill not in current:
                        st.session_state["soft_skills"] = f"{current}{sep}{skill}"
                    st.session_state["suggested_soft_skills"] = [
                        s for s in soft_list if s != skill
                    ]
                    st.rerun()


def benefits_compensation_page():
    """Benefits page: Compensation and benefits details, with suggestions for perks."""
    lang = st.session_state.get("lang", "en")
    st.header(
        "💰 Benefits & Compensation" if lang != "de" else "💰 Vergütung & Vorteile"
    )
    render_followups_for(
        [
            "compensation.salary_min",
            "compensation.salary_max",
            "compensation.benefits",
            "compensation.healthcare_plan",
            "compensation.pension_plan",
            "employment.work_policy",
            "employment.travel_required",
        ]
    )


st.session_state["employment.job_type"] = st.selectbox(
    "Employment Type" if lang != "de" else "Anstellungsart",
    [
        "Full-time",
        "Part-time",
        "Contract",
        "Temporary",
        "Internship",
        "Apprenticeship",
        "Freelance",
        "Fixed-term",
    ],
    index=(
        0
        if not st.session_state.get(
            "employment.job_type"
        )  # set default or current value
        else max(
            0,
            [
                "Full-time",
                "Part-time",
                "Contract",
                "Temporary",
                "Internship",
                "Apprenticeship",
                "Freelance",
                "Fixed-term",
            ].index(st.session_state["employment.job_type"]),
        )
    ),
    key="employment.job_type",
)
st.session_state["employment.work_policy"] = st.selectbox(
    "Work Policy" if lang != "de" else "Arbeitsmodell",
    ["Onsite", "Hybrid", "Remote"],
    index=(
        0
        if not st.session_state.get("employment.work_policy")
        else max(
            0,
            ["Onsite", "Hybrid", "Remote"].index(
                st.session_state["employment.work_policy"]
            ),
        )
    ),
    key="employment.work_policy",
)
st.session_state["employment.travel_required"] = st.checkbox(
    "Travel required" if lang != "de" else "Reise erforderlich",
    value=bool(st.session_state.get("employment.travel_required", False)),
    key="employment.travel_required",
)
# Salary fields
sal_provided = st.checkbox(
    "Salary information provided" if lang != "de" else "Gehaltsspanne angeben",
    value=bool(st.session_state.get("compensation.salary_provided", True)),
    key="compensation.salary_provided",
)
if sal_provided:
    # Show min, max, currency, period inputs
    cols = st.columns([1, 1, 1, 1])
    with cols[0]:
        st.session_state["compensation.salary_min"] = st.number_input(
            "Salary Min",
            value=st.session_state.get("compensation.salary_min", 0),
            step=500,
            min_value=0,
            key="compensation.salary_min",
        )
    with cols[1]:
        st.session_state["compensation.salary_max"] = st.number_input(
            "Salary Max",
            value=st.session_state.get("compensation.salary_max", 0),
            step=500,
            min_value=0,
            key="compensation.salary_max",
        )
    with cols[2]:
        st.session_state["compensation.salary_currency"] = st.selectbox(
            "Currency" if lang != "de" else "Währung",
            ["EUR", "USD", "GBP", "CHF", "SEK", "NOK", "DKK", "PLN", "CZK"],
            index=(
                0
                if not st.session_state.get("compensation.salary_currency")
                else max(
                    0,
                    [
                        "EUR",
                        "USD",
                        "GBP",
                        "CHF",
                        "SEK",
                        "NOK",
                        "DKK",
                        "PLN",
                        "CZK",
                    ].index(st.session_state["compensation.salary_currency"]),
                )
            ),
            key="compensation.salary_currency",
        )
    with cols[3]:
        st.session_state["compensation.salary_period"] = st.selectbox(
            "Period",
            ["year", "month", "day", "hour"],
            index=(
                0
                if not st.session_state.get("compensation.salary_period")
                else max(
                    0,
                    ["year", "month", "day", "hour"].index(
                        st.session_state["compensation.salary_period"]
                    ),
                )
            ),
            key="compensation.salary_period",
        )
    benefits_label = "Benefits/Perks" if lang != "de" else "Vorteile/Extras"
    # Merge deprecated benefit keys into the schema-aligned field.
    merged = st.session_state.get("compensation.benefits", "")
    for legacy in ("health_benefits", "retirement_benefits"):
        extra = st.session_state.pop(legacy, "")
        if extra:
            merged = f"{merged}\n{extra}" if merged else extra
    st.session_state["compensation.benefits"] = merged
    editable_draggable_list("compensation.benefits", benefits_label)
    st.session_state["learning_opportunities"] = st.text_area(
        (
            "Learning & Development Opportunities"
            if lang != "de"
            else "Weiterbildungs- und Entwicklungsmöglichkeiten"
        ),
        st.session_state.get("learning_opportunities", ""),
        height=70,
    )
    st.session_state["remote_policy"] = st.text_input(
        "Remote Work Policy" if lang != "de" else "Richtlinie für Fernarbeit",
        st.session_state.get("remote_policy", ""),
    )
    st.session_state["travel_required"] = st.text_input(
        "Travel Requirements" if lang != "de" else "Reisebereitschaft",
        st.session_state.get("travel_required", ""),
    )
    benefit_btn_col, benefit_model_col = st.columns([3, 2])
    with benefit_model_col:
        benefit_model_label = st.selectbox(
            "Model",
            list(MODEL_OPTIONS.keys()),
            key="benefit_model",
        )
    with benefit_btn_col:
        suggest_label = (
            "💡 Suggest Benefits" if lang != "de" else "💡 Benefits vorschlagen"
        )
        if st.button(suggest_label):
            model_name = MODEL_OPTIONS[benefit_model_label]
            with st.spinner(
                (
                    f"Suggesting common benefits with {benefit_model_label}..."
                    if lang != "de"
                    else f"Gängige Benefits werden mit {benefit_model_label} vorgeschlagen..."
                )
            ):
                title = st.session_state.get("position.job_title", "")
                industry = st.session_state.get("company.industry", "")
                existing = st.session_state.get("compensation.benefits", "")
                try:
                    benefit_suggestions = suggest_benefits(
                        title,
                        industry,
                        existing_benefits=existing,
                        model=model_name,
                    )
                except Exception:  # pragma: no cover - network failure
                    warn = (
                        "⚠️ Could not generate benefit suggestions."
                        if lang != "de"
                        else "⚠️ Konnte keine Benefit-Vorschläge generieren."
                    )
                    st.warning(warn)
                    benefit_suggestions = []
            if benefit_suggestions:
                cast(dict[str, Any], st.session_state)[
                    "suggested_benefits"
                ] = benefit_suggestions
                st.success(
                    "✔️ Benefit suggestions generated. Click to add them."
                    if lang != "de"
                    else "✔️ Benefit-Vorschläge generiert. Klicken Sie, um sie hinzuzufügen."
                )
            else:
                st.warning(
                    "No benefit suggestions available at the moment."
                    if lang != "de"
                    else "Derzeit keine Benefit-Vorschläge verfügbar."
                )
    # Display benefit suggestions as chips if available
    benefit_suggestions = st.session_state.get("suggested_benefits", [])
    if benefit_suggestions:
        cols = st.columns(len(benefit_suggestions))
        for k, (col, perk) in enumerate(zip(cols, benefit_suggestions)):
            with col:
                if st.button(perk, key=f"benefit_sugg_{k}"):
                    current = st.session_state.get("compensation.benefits", "")
                    sep = "\n" if current else ""
                    if perk not in current:
                        st.session_state["compensation.benefits"] = (
                            f"{current}{sep}{perk}"
                        )
                    # Remove added perk from suggestions list
                    cast(dict[str, Any], st.session_state)["suggested_benefits"] = [
                        b for b in benefit_suggestions if b != perk
                    ]
                    st.rerun()


def recruitment_process_page():
    """Process page: Details about the recruitment process (interview rounds, notes)."""
    lang = st.session_state.get("lang", "en")
    st.header("🏁 Recruitment Process" if lang != "de" else "🏁 Einstellungsprozess")
    render_followups_for(["interview_stages", "process_notes"])
    st.session_state["interview_stages"] = int(
        st.number_input(
            (
                "Number of Interview Rounds"
                if lang != "de"
                else "Anzahl der Interviewrunden"
            ),
            min_value=0,
            step=1,
            value=int(st.session_state.get("interview_stages", 0)),
        )
    )
    st.session_state["process_notes"] = st.text_area(
        (
            "Additional Hiring Process Notes"
            if lang != "de"
            else "Weitere Hinweise zum Prozess"
        ),
        st.session_state.get("process_notes", ""),
        height=80,
    )


def summary_outputs_page():
    """Summary page: Display a summary of collected fields and provide output generation (job ad, interview guide, boolean query)."""
    lang = st.session_state.get("lang", "en")
    normalise_state(
        reapply_aliases=False
    )  # Final normalization (do not reapply alias values here)
    st.header(
        "📊 Summary & Outputs" if lang != "de" else "📊 Zusammenfassung & Ergebnisse"
    )
    if st.session_state.get("company_logo"):
        st.image(st.session_state["company_logo"], width=150)
    if st.session_state.get("company.name"):
        st.subheader(st.session_state["company.name"])
    if st.session_state.get("company_style_guide"):
        st.markdown(f"**Style Guide:** {st.session_state['company_style_guide']}")
    # Show ESCO occupation classification if available
    if st.session_state.get("occupation_label"):
        occ_label = st.session_state["occupation_label"]
        occ_group = st.session_state.get("occupation_group", "")
        if lang == "de":
            st.write(f"**Erkannte ESCO-Berufsgruppe:** {occ_label} ({occ_group})")
        else:
            st.write(f"**Identified ESCO Occupation:** {occ_label} ({occ_group})")
    tab_labels = [
        cat["de"] if lang == "de" else cat["en"] for cat in SUMMARY_CATEGORIES
    ]
    tabs = st.tabs(tab_labels)
    for tab, category in zip(tabs, SUMMARY_CATEGORIES):
        with tab:
            for field in category["fields"]:
                value = st.session_state.get(field, "")
                is_missing = not value and field in CRITICAL_FIELDS
                if value or is_missing:
                    label = field.replace("_", " ").title()
                    render_summary_input(field, label, is_missing)
    # Model selection and document generation
    model = model_selector()

    tone_label = "Job ad tone" if lang != "de" else "Tonfall der Stellenanzeige"
    tone_labels = [
        choice["en"] if lang != "de" else choice["de"]
        for choice in TONE_CHOICES.values()
    ]
    default_job_tone = (
        TONE_CHOICES["diversity"]["en"]
        if lang != "de"
        else TONE_CHOICES["diversity"]["de"]
    )
    selected_job_label = st.selectbox(
        tone_label,
        tone_labels,
        index=tone_labels.index(default_job_tone),
        key="job_ad_tone_label",
    )
    job_tone_key = next(
        k
        for k, v in TONE_CHOICES.items()
        if v["en"] == selected_job_label or v["de"] == selected_job_label
    )
    st.session_state["job_ad_tone"] = TONE_CHOICES[job_tone_key][
        "tone_de" if lang.startswith("de") else "tone_en"
    ]

    generate_label = (
        "🎯 Generate Final Job Ad"
        if lang != "de"
        else "🎯 Finale Stellenanzeige erstellen"
    )
    if st.button(generate_label):
        with st.spinner(
            "Generating job advertisement..."
            if lang != "de"
            else "Stellenanzeige wird erstellt..."
        ):
            try:
                job_ad_text = generate_job_ad(
                    st.session_state,
                    tone=st.session_state.get("job_ad_tone"),
                    model=model,
                )
            except Exception:  # pragma: no cover - network failure
                err = (
                    "❌ Failed to generate job ad. Please try again later."
                    if lang != "de"
                    else "❌ Stellenanzeige konnte nicht erstellt werden. Bitte später erneut versuchen."
                )
                st.error(err)
                job_ad_text = ""
        if job_ad_text:
            st.session_state["job_ad_text"] = job_ad_text

    job_ad_text = st.session_state.get("job_ad_text")
    if job_ad_text:
        st.subheader(
            (
                "Generated Job Advertisement"
                if lang != "de"
                else "Erstellte Stellenanzeige"
            )
        )
        st.write(job_ad_text)
        findings = scan_bias_language(job_ad_text, lang)
        if findings:
            warn = (
                "Potentially biased terms detected:"
                if lang != "de"
                else "Möglicherweise vorbelastete Begriffe gefunden:"
            )
            st.warning(warn)
            for item in findings:
                st.markdown(f"- `{item['term']}` → {item['suggestion']}")
        seo = seo_optimize(job_ad_text)
        if seo["keywords"]:
            st.markdown(f"**SEO Keywords:** `{', '.join(seo['keywords'])}`")
        if seo["meta_description"]:
            st.markdown(f"**Meta Description:** {seo['meta_description']}")
        fmt_label = "Download format" if lang != "de" else "Download-Format"
        job_fmt = st.selectbox(
            fmt_label,
            ["markdown", "docx", "pdf", "json"],
            key="job_ad_format",
        )
        data, mime, ext = prepare_download_data(
            job_ad_text,
            job_fmt,
            key="job_ad",
            title=st.session_state.get("job_title"),
        )
        dl_label = (
            "💾 Download Job Ad" if lang != "de" else "💾 Stellenanzeige herunterladen"
        )
        st.download_button(
            dl_label,
            data=data,
            file_name=f"job_ad.{ext}",
            mime=mime,
        )
        feedback_label = (
            "Refinement instructions" if lang != "de" else "Anpassungshinweise"
        )
        feedback = st.text_input(feedback_label, key="job_ad_feedback")
        update_label = (
            "🔄 Update Job Ad" if lang != "de" else "🔄 Stellenanzeige aktualisieren"
        )
        if st.button(update_label) and feedback:
            updated = refine_document(job_ad_text, feedback, model=model)
            st.session_state["job_ad_text"] = updated
            st.session_state["job_ad_feedback"] = ""
        what_label = "❓ What happened?" if lang != "de" else "❓ Was ist passiert?"
        if st.button(what_label, key="job_ad_what"):
            explanation = what_happened(
                st.session_state,
                st.session_state.get("job_ad_text", ""),
                doc_type="job ad",
                model=model,
            )
            st.info(explanation)
        log_event(f"JOB_AD by {st.session_state.get('user', 'anonymous')}")

    q_label = (
        "Number of interview questions"
        if lang != "de"
        else "Anzahl der Interviewfragen"
    )
    num_questions = st.slider(
        q_label,
        min_value=3,
        max_value=10,
        value=5,
        key="num_questions",
    )
    guide_tone_label = (
        "Interview guide tone" if lang != "de" else "Tonfall des Leitfadens"
    )
    guide_tone_labels = [
        choice["en"] if lang != "de" else choice["de"]
        for choice in TONE_CHOICES.values()
    ]
    default_guide_tone = (
        TONE_CHOICES["diversity"]["en"]
        if lang != "de"
        else TONE_CHOICES["diversity"]["de"]
    )
    selected_guide_label = st.selectbox(
        guide_tone_label,
        guide_tone_labels,
        index=guide_tone_labels.index(default_guide_tone),
        key="guide_tone_label",
    )
    guide_tone_key = next(
        k
        for k, v in TONE_CHOICES.items()
        if v["en"] == selected_guide_label or v["de"] == selected_guide_label
    )
    st.session_state["interview_guide_tone"] = TONE_CHOICES[guide_tone_key][
        "tone_de" if lang.startswith("de") else "tone_en"
    ]
    generate_label = (
        "📝 Generate Interview Guide"
        if lang != "de"
        else "📝 Interviewleitfaden erstellen"
    )
    if st.button(generate_label):
        title = st.session_state.get("job_title", "")
        tasks = st.session_state.get("tasks", "") or st.session_state.get(
            "responsibilities",
            "",
        )
        with st.spinner(
            "Generating interview guide..."
            if lang != "de"
            else "Leitfaden wird erstellt..."
        ):
            try:
                guide = generate_interview_guide(
                    title,
                    tasks,
                    audience="hiring managers",
                    num_questions=num_questions,
                    lang=lang,
                    company_culture=st.session_state.get("company.culture", ""),
                    tone=st.session_state.get("interview_guide_tone"),
                    model=model,
                )
            except Exception:  # pragma: no cover - network failure
                err = (
                    "❌ Failed to generate interview guide. Please try again later."
                    if lang != "de"
                    else "❌ Leitfaden konnte nicht erstellt werden. Bitte später erneut versuchen."
                )
                st.error(err)
                guide = ""
        if guide:
            st.session_state["interview_guide"] = guide

    guide = st.session_state.get("interview_guide")
    if guide:
        st.subheader(
            (
                "Interview Guide & Scoring Rubrics"
                if lang != "de"
                else "Leitfaden für Vorstellungsgespräch & Bewertungsrichtlinien"
            )
        )
        st.write(guide)
        fmt_label = "Download format" if lang != "de" else "Download-Format"
        guide_fmt = st.selectbox(
            fmt_label,
            ["markdown", "docx", "pdf", "json"],
            key="guide_format",
        )
        data, mime, ext = prepare_download_data(
            guide,
            guide_fmt,
            key="interview_guide",
            title=st.session_state.get("job_title"),
        )
        dl_label = (
            "💾 Download Interview Guide"
            if lang != "de"
            else "💾 Leitfaden herunterladen"
        )
        st.download_button(
            dl_label,
            data=data,
            file_name=f"interview_guide.{ext}",
            mime=mime,
        )
        feedback_label = (
            "Refinement instructions" if lang != "de" else "Anpassungshinweise"
        )
        feedback = st.text_input(feedback_label, key="guide_feedback")
        update_label = (
            "🔄 Update Interview Guide"
            if lang != "de"
            else "🔄 Interviewleitfaden aktualisieren"
        )
        if st.button(update_label) and feedback:
            updated = refine_document(guide, feedback, model=model)
            st.session_state["interview_guide"] = updated
            st.session_state["guide_feedback"] = ""
        what_label = "❓ What happened?" if lang != "de" else "❓ Was ist passiert?"
        if st.button(what_label, key="guide_what"):
            explanation = what_happened(
                st.session_state,
                st.session_state.get("interview_guide", ""),
                doc_type="interview guide",
                model=model,
            )
            st.info(explanation)
        log_event(f"INTERVIEW_GUIDE by {st.session_state.get('user', 'anonymous')}")
    # Always display a suggested Boolean search query for recruiters
    if st.session_state.get("job_title") or st.session_state.get("hard_skills"):
        skills = (
            st.session_state.get("hard_skills", "")
            + "\n"
            + st.session_state.get("soft_skills", "")
        ).splitlines()
        skills = [s.strip() for s in skills if s.strip()]
        with st.expander(
            "Customize Boolean Search" if lang != "de" else "Boolean-Suche anpassen"
        ):
            include_title = st.checkbox(
                "Include job title" if lang != "de" else "Jobtitel einbeziehen",
                value=bool(st.session_state.get("job_title")),
            )
            title_synonyms_input = st.text_input(
                (
                    "Title synonyms (comma-separated)"
                    if lang != "de"
                    else "Titel-Synonyme (durch Komma getrennt)"
                ),
            )
            selected_skills = st.multiselect(
                "Skills to include" if lang != "de" else "Skills einbeziehen",
                options=skills,
                default=skills,
            )
        bool_query = build_boolean_query(
            st.session_state.get("job_title", ""),
            selected_skills,
            include_title=include_title,
            title_synonyms=[
                s.strip() for s in title_synonyms_input.split(",") if s.strip()
            ],
        )
        if bool_query:
            st.info(f"**Boolean Search Query:** `{bool_query}`")


def log_event(event_text: str):
    """Append an event entry to the usage log with a timestamp."""
    ensure_logs_dir()
    import datetime

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] {event_text}\n"
    try:
        with open("logs/usage.log", "a", encoding="utf-8") as f:
            f.write(entry)
    except Exception:
        # If file write fails (e.g., no permission), print to console
        print(entry)
