# ui_views/tech_overview.py
"""Streamlit-Seite: Technology Deep Dive & Wizard Flow

Für IT‑Spezialisten und Entscheider bietet diese Seite einen kompakten, aber
technisch fundierten Überblick über den *Cognitive Needs*-Stack sowie eine visuelle
Darstellung des mehrstufigen Wizard‑Flows (Discovery‑Process).
Ein Sprach‑ und Zielgruppenumschalter sorgt dafür, dass Texte sowohl für ein
Fach‑Publikum (Tech‑interessiert/Tech‑savvy) als auch für nicht‑technische
Stakeholder (Allgemein verständlich/General public) optimal angepasst werden.
"""

import streamlit as st

from utils.i18n import tr
from utils.session import bootstrap_session, migrate_legacy_keys

bootstrap_session()
migrate_legacy_keys()

# ---------------------------------------------------------------------------
# Language & audience toggle
# ---------------------------------------------------------------------------
session_lang = st.session_state.get("lang", "de")
lang_label = st.radio(
    tr("🌐 Sprache", "🌐 Language", lang=session_lang),
    ("Deutsch", "English"),
    horizontal=True,
    key="tech_lang",
)
lang = "de" if lang_label == "Deutsch" else "en"
st.session_state["lang"] = lang
audience = st.radio(
    tr("🎯 Zielgruppe", "🎯 Audience", lang=lang),
    (
        tr("Tech-interessiert", "Tech-savvy", lang=lang),
        tr("Allgemein verständlich", "General public", lang=lang),
    ),
    horizontal=True,
    key="audience",
)

TECH_AUDIENCE = tr("Tech-interessiert", "Tech-savvy", lang=lang)

# ---------------------------------------------------------------------------
# Technology catalogue
# ---------------------------------------------------------------------------
tech_info = {
    "Deutsch": {
        "Tech-interessiert": [
            (
                "Retrieval-Augmented Generation (RAG)",
                "FAISS bzw. künftig ChromaDB/Weaviate liefern Vektor‑Suche über mehr als 400 000 ESCO‑Skills und Domain‑Korpora; eine hauseigene Orchestrierung koordiniert Extraktion und RAG.",
            ),
            (
                "Eigenes Agenten-Framework & OpenAI Function Calling",
                "Deterministische Tool‑Aufrufe (PDF‑Parser, ESCO‑Lookup, Markdown‑Renderer) über unser leichtgewichtiges Agenten‑Framework mit JSON‑Schemas für robustes Error‑Handling.",
            ),
            (
                "Embedding‑Model",
                "OpenAI *text-embedding-3-large* (3 072 Dimensionen) liefert stabilere, mehrsprachige Treffer;"
                " trotz höherer Kosten behalten wir „Small“ als Fallback vor.",
            ),
            (
                "Streaming Responses",
                "OpenAI `responses.stream` + Streamlit-Platzhalter liefern tokenweises UI‑Streaming (< 300 ms TTFB) für eine flüssige Nutzer‑Erfahrung.",
            ),
            (
                "CI/CD Pipeline",
                "GitHub Actions → Docker → Terraform; Canary‑Deployments auf Kubernetes mit automatischem Rollback.",
            ),
            (
                "Observability & Kosten‑Tracking",
                "OpenTelemetry Tracing + Prometheus/Grafana; Token‑Kosten pro Request im UI sichtbar.",
            ),
            (
                "Security Layer",
                "OIDC‑basiertes Secrets‑Management und zweistufige Rollenlogik (Recruiter vs. Admin).",
            ),
            (
                "Event‑Driven Wizard Flow",
                "Finite‑State‑Machine triggert dynamische Fragen und speichert Zwischenergebnisse als JSON‑Graph.",
            ),
            (
                "Infrastructure as Code",
                "Vollständige Cloud‑Provisionierung in Terraform 1.7 mit Drift‑Detection.",
            ),
        ],
        "Allgemein verständlich": [
            (
                "Künstliche Intelligenz",
                "Cognitive Needs nutzt modernste KI, um Stellenanforderungen präzise zu verstehen und passende Kompetenzen vorzuschlagen.",
            ),
            (
                "Schlaue Suche",
                "Eine Spezial‑Suche findet blitzschnell relevante Fähigkeiten und Aufgaben.",
            ),
            (
                "Fließende Antworten",
                "Antworten erscheinen Stück für Stück – Wartezeiten verkürzen sich.",
            ),
            (
                "Automatische Updates",
                "Neue Versionen werden im Hintergrund eingespielt, ohne Ausfallzeiten.",
            ),
            (
                "Sicherheit & Datenschutz",
                "Aktuelle Standards schützen vertrauliche Daten konsequent.",
            ),
        ],
    },
    "English": {
        "Tech-savvy": [
            (
                "Retrieval-Augmented Generation (RAG)",
                "FAISS – future upgrade to ChromaDB/Weaviate – provides vector search across 400 k+ ESCO skills & domain corpora, coordinated by our custom extraction/RAG orchestrator.",
            ),
            (
                "Custom Agent Harness & OpenAI Function Calling",
                "Deterministic tool invocation (PDF parser, ESCO lookup, Markdown renderer) via our lightweight agent harness with strict JSON schemas for resilient error handling.",
            ),
            (
                "Embedding Model",
                "OpenAI *text-embedding-3-large* (3,072-dim vectors) boosts recall & cross-lingual quality;"
                " the pricier tier stays optional thanks to a retained *-3-small* fallback.",
            ),
            (
                "Streaming Responses",
                "OpenAI `responses.stream` combined with Streamlit placeholders enables sub‑300 ms TTFB and token-level updates for a snappy UX.",
            ),
            (
                "CI/CD Pipeline",
                "GitHub Actions → Docker → Terraform; canary deployments on Kubernetes with auto‑rollback.",
            ),
            (
                "Observability & Cost Governance",
                "OpenTelemetry tracing + Prometheus/Grafana; token cost per request surfaced in the UI.",
            ),
            (
                "Security Layer",
                "OIDC‑backed secret management and dual role model (Recruiter vs. Admin).",
            ),
            (
                "Event‑Driven Wizard Flow",
                "Finite state machine triggers dynamic questions and stores interim results as a JSON graph.",
            ),
            (
                "Infrastructure as Code",
                "Full cloud provisioning in Terraform 1.7 with automatic drift detection.",
            ),
        ],
        "General public": [
            (
                "Artificial Intelligence",
                "Cognitive Needs uses cutting‑edge AI to understand job requirements and suggest matching skills.",
            ),
            (
                "Smart Search",
                "A specialised search engine instantly finds relevant skills and tasks.",
            ),
            ("Live Answers", "Replies appear gradually, so you don’t have to wait."),
            (
                "Automatic Updates",
                "New versions are rolled out silently with no downtime.",
            ),
            (
                "Security & Privacy",
                "Modern standards keep your data safe at every step.",
            ),
        ],
    },
}

# ---------------------------------------------------------------------------
# Wizard flow definition
# ---------------------------------------------------------------------------
wizard_steps = [
    ("Intake", tr("Job‑Titel & Dokumente", "Job title & docs", lang=lang)),
    ("Parse", tr("AI‑Parsing", "AI parsing", lang=lang)),
    ("Enrich", tr("ESCO‑Mapping", "ESCO mapping", lang=lang)),
    ("QA", tr("Dynamisches Q&A", "Dynamic Q&A", lang=lang)),
    ("Draft", tr("Profil‑Entwurf", "Draft profile", lang=lang)),
    ("Review", tr("Freigabe", "Review", lang=lang)),
    ("Export", tr("Export (PDF/MD)", "Export (PDF/MD)", lang=lang)),
]


def render_wizard_graph() -> None:
    dot = (
        "digraph wizard {\n"
        "  rankdir=LR;\n"
        '  node [shape=box style="rounded,filled" fontname=Helvetica color=#5b8def fillcolor=#eef4ff];\n'
    )
    for step, label in wizard_steps:
        dot += f'  {step} [label="{label}"];\n'
    for idx in range(len(wizard_steps) - 1):
        dot += f"  {wizard_steps[idx][0]} -> {wizard_steps[idx + 1][0]};\n"
    dot += "}"
    st.graphviz_chart(dot)


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------
if audience == TECH_AUDIENCE:
    title = tr("🛠️ Technischer Deep Dive", "🛠️ Technology Deep Dive", lang=lang)
else:
    title = tr("🛠️ Technologischer Überblick", "🛠️ Technology Overview", lang=lang)

st.title(title)

intro = tr(
    (
        "Nachfolgend findest du die Schlüsseltechnologien, die Cognitive Needs antreiben, "
        "sowie eine Grafik, die den Discovery‑Prozess Schritt für Schritt veranschaulicht."
    ),
    (
        "Below you can explore the core technologies powering Cognitive Needs together with a graph "
        "illustrating each step of the discovery process."
    ),
    lang=lang,
)

st.markdown(intro)

# ─── Technology cards ───
for tech, desc in tech_info[lang_label][audience]:
    st.markdown(f"### 🔹 {tech}\n{desc}")

# ─── Wizard flow graph for tech audience ───
if audience == TECH_AUDIENCE:
    st.divider()
    st.markdown(tr("#### 🔄 Wizard‑Flow & State Machine", "#### 🔄 Wizard Flow & State Machine", lang=lang))
    render_wizard_graph()

st.divider()

st.info(
    tr(
        "Die gezeigte Architektur ist modular erweiterbar und bildet eine zukunftssichere Basis für hochskalierbare Recruiting‑Workflows.",
        "The presented stack is modular and future‑proof, enabling highly scalable recruiting workflows with minimal operational overhead.",
        lang=lang,
    )
)
