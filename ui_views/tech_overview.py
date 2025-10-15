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

from utils.session import bootstrap_session, migrate_legacy_keys

bootstrap_session()
migrate_legacy_keys()

# ---------------------------------------------------------------------------
# Language & audience toggle
# ---------------------------------------------------------------------------
lang_label = st.radio(
    "🌐 Sprache / Language",
    ("Deutsch", "English"),
    horizontal=True,
    key="tech_lang",
)
lang = "de" if lang_label == "Deutsch" else "en"
audience = st.radio(
    "🎯 Zielgruppe / Audience",
    (("Tech-interessiert", "Allgemein verständlich") if lang == "de" else ("Tech-savvy", "General public")),
    horizontal=True,
    key="audience",
)

TECH_AUDIENCE = "Tech-interessiert" if lang == "de" else "Tech-savvy"

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
    ("Intake", "Job‑Titel & Dokumente" if lang == "de" else "Job title & docs"),
    ("Parse", "AI‑Parsing"),
    ("Enrich", "ESCO‑Mapping"),
    ("QA", "Dynamic Q&A"),
    ("Draft", "Profil‑Entwurf" if lang == "de" else "Draft profile"),
    ("Review", "Freigabe" if lang == "de" else "Review"),
    ("Export", "Export (PDF/MD)"),
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
if audience == TECH_AUDIENCE and lang == "de":
    title = "🛠️ Technischer Deep Dive"
elif audience == TECH_AUDIENCE:
    title = "🛠️ Technology Deep Dive"
elif lang == "de":
    title = "🛠️ Technologischer Überblick"
else:
    title = "🛠️ Technology Overview"

st.title(title)

intro = (
    "Nachfolgend findest du die Schlüsseltechnologien, die Cognitive Needs antreiben, "
    "sowie eine Grafik, die den Discovery‑Prozess Schritt für Schritt veranschaulicht."
    if lang == "de"
    else "Below you can explore the core technologies powering Cognitive Needs together with a graph "
    "illustrating each step of the discovery process."
)

st.markdown(intro)

# ─── Technology cards ───
for tech, desc in tech_info[lang_label][audience]:
    st.markdown(f"### 🔹 {tech}\n{desc}")

# ─── Wizard flow graph for tech audience ───
if audience == TECH_AUDIENCE:
    st.divider()
    st.markdown("#### 🔄 Wizard‑Flow & State Machine" if lang == "de" else "#### 🔄 Wizard Flow & State Machine")
    render_wizard_graph()

st.divider()

st.info(
    "Die gezeigte Architektur ist modular erweiterbar und bildet eine zukunftssichere Basis für hochskalierbare Recruiting‑Workflows."
    if lang == "de"
    else "The presented stack is modular and future‑proof, enabling highly scalable recruiting workflows with minimal operational overhead."
)
