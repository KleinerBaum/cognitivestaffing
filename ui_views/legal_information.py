"""Streamlit page that collects legal notices and licensing requirements."""

from __future__ import annotations

from typing import List, Tuple, TypedDict

import streamlit as st

LegalSection = Tuple[str, str]


class LanguageContent(TypedDict):
    """Structure for localized legal content."""

    intro: str
    sections: List[LegalSection]
    footnote: str


def render_sections(sections: List[LegalSection]) -> None:
    """Render the legal sections in order."""
    for title, body in sections:
        st.subheader(title)
        st.markdown(body)


def main() -> None:
    """Render the legal information page."""
    st.title("📜 Legal Information / Rechtliche Hinweise")

    lang_label = st.radio(
        "🌐 Sprache / Language",
        ("Deutsch", "English"),
        horizontal=True,
        key="legal_lang",
    )

    content: dict[str, LanguageContent] = {
        "Deutsch": {
            "intro": (
                "Diese Seite bündelt die wichtigsten rechtlichen Hinweise, damit die "
                "Veröffentlichung der Cognitive‑Needs‑App den geltenden Richtlinien "
                "entspricht. Bitte passe Kontaktangaben, Unternehmensdaten und "
                "eventuelle lokale Anforderungen nach Bedarf an."
            ),
            "sections": [
                (
                    "Anbieterkennzeichnung (Impressum)",
                    """
                    **Cognitive Needs GmbH**  \
                    Musterstraße 12  \
                    12345 Berlin  \
                    Deutschland

                    Telefon: +49 30 1234567  \
                    E-Mail: contact@cognitive-needs.example

                    Geschäftsführung: Alex Example  \
                    Handelsregister: Amtsgericht Berlin HRB 123456  \
                    USt-IdNr.: DE123456789
                    """,
                ),
                (
                    "Kontakt & Support",
                    """
                    Für Support-Anfragen oder Hinweise zu Inhalten wenden Sie sich bitte an  \
                    **support@cognitive-needs.example**. Wir beantworten Anfragen in der Regel innerhalb von zwei Werktagen.
                    """,
                ),
                (
                    "Nutzung der Anwendung",
                    """
                    - Die bereitgestellten Analysen und Inhalte ersetzen keine rechtliche Beratung.  \
                    - Nutzer:innen sind dafür verantwortlich, eingegebene Daten auf Richtigkeit und Vollständigkeit zu prüfen.  \
                    - Wir behalten uns vor, Funktionen kurzfristig anzupassen, um regulatorische Anforderungen zu erfüllen.
                    """,
                ),
                (
                    "Datenschutz & Vertraulichkeit",
                    """
                    Wir verarbeiten personenbezogene Daten ausschließlich zum Zweck der Bedarfsermittlung und Profilgenerierung.
                    Weitere Details können in einer separaten Datenschutzrichtlinie erläutert werden. Bitte stellen Sie sicher,
                    dass eine entsprechende Datenschutzerklärung für Ihre Zielmärkte verlinkt ist.
                    """,
                ),
                (
                    "ESCO-Lizenzhinweis",
                    """
                    Gemäß der Entscheidung der Kommission vom 12. Dezember 2011 über die Weiterverwendung von Dokumenten der
                    Kommission (2011/833/EU) kann die ESCO-Klassifikation kostenlos von jeder interessierten Partei für jegliche
                    Zwecke heruntergeladen, genutzt, reproduziert und wiederverwendet werden. Sie darf mit bestehenden
                    Taxonomien oder Klassifikationen verknüpft werden, um Ergänzungen oder Zuordnungen vorzunehmen. Jegliche
                    Nutzung unterliegt den folgenden Bedingungen:

                    1) Die Nutzung von ESCO ist durch Veröffentlichung der nachstehenden Erklärung kenntlich zu machen:

                       - Für Dienste, Tools und Anwendungen, die ESCO ganz oder teilweise integrieren: "This service uses the
                         ESCO classification of the European Commission."
                       - Für andere Dokumente wie Studien, Analysen oder Berichte, die ESCO verwenden: "This publication uses the
                         ESCO classification of the European Commission."

                    2) Jede geänderte oder angepasste Version von ESCO muss eindeutig als solche kenntlich gemacht werden.

                    Bitte beachten Sie, dass nicht garantiert werden kann, dass die auf der ESCO-Website oder in den
                    heruntergeladenen Dateien bereitgestellten Informationen korrekt, aktuell oder vollständig sind. Gleiches gilt
                    für die Qualität der Übersetzungen innerhalb der Klassifikation. Die Kommission haftet nicht für Folgen, die
                    sich aus der Nutzung, Wiederverwendung oder dem Einsatz von ESCO ergeben.

                    3) Der*die Nutzer*in stimmt zu, dass die im unten stehenden Formular übermittelten Informationen für die in
                    Abschnitt 2-a genannten Zwecke verwendet werden dürfen.

                    > **Originaltext (English):**
                    > In accordance with the Commission Decision of 12 December 2011 on the reuse of Commission documents
                    > (2011/833/EU), the ESCO classification can be downloaded, used, reproduced and reused for any purpose and by
                    > any interested party free of charge. It may be linked with existing taxonomies or classifications for
                    > supplementing and mapping purposes. Any use is subject to the following conditions:
                    >
                    > 1) The use of ESCO shall be acknowledged by publishing the statement below:
                    >
                    >    - For services, tools and applications integrating totally or partially ESCO: "This service uses the ESCO
                    >      classification of the European Commission."
                    >    - For other documents such as studies, analysis or reports making use of ESCO: "This publication uses the
                    >      ESCO classification of the European Commission."
                    >
                    > 2) Any modified or adapted version of ESCO must be clearly indicated as such.
                    >
                    > Please, be aware that it cannot be guaranteed that the information provided on the ESCO website or in the
                    > downloaded files is accurate, up-to-date or complete. The same applies to the quality of translated terms
                    > within the classification. The Commission shall not be liable for any consequence stemming from the use,
                    > reuse or deployment of the ESCO
                    >
                    > 3) The user agrees that the information submitted in the form below may be used for purposes indicated in
                    > the section 2-a.
                    """,
                ),
                (
                    "Haftungsausschluss",
                    """
                    Trotz sorgfältiger inhaltlicher Kontrolle übernehmen wir keine Haftung für die Inhalte externer Links. Für den
                    Inhalt der verlinkten Seiten sind ausschließlich deren Betreiber verantwortlich.
                    """,
                ),
            ],
            "footnote": "Letzte Aktualisierung: März 2024. Bitte passen Sie das Datum an, wenn Änderungen vorgenommen werden.",
        },
        "English": {
            "intro": (
                "This page consolidates the key legal information required to publish the Cognitive Needs app in a compliant way. "
                "Adjust company details, contacts, and market-specific clauses as needed before going live."
            ),
            "sections": [
                (
                    "Publisher information (Imprint)",
                    """
                    **Cognitive Needs GmbH**  \
                    Sample Street 12  \
                    10117 Berlin  \
                    Germany

                    Phone: +49 30 1234567  \
                    Email: contact@cognitive-needs.example

                    Managing Director: Alex Example  \
                    Commercial register: Local court Berlin HRB 123456  \
                    VAT ID: DE123456789
                    """,
                ),
                (
                    "Contact & Support",
                    """
                    Please direct support requests or content notices to  \
                    **support@cognitive-needs.example**. We usually respond within two business days.
                    """,
                ),
                (
                    "Terms of use",
                    """
                    - The analyses and documents generated by the app do not replace professional legal advice.  \
                    - Users remain responsible for verifying the accuracy and completeness of any data they submit.  \
                    - Features may change at short notice to remain compliant with evolving regulations.
                    """,
                ),
                (
                    "Data protection & confidentiality",
                    """
                    Personal data is processed solely to assess hiring needs and to generate structured vacancy profiles. Provide a
                    link to your full privacy policy to comply with local data protection requirements.
                    """,
                ),
                (
                    "ESCO licensing notice",
                    """
                    In accordance with the Commission Decision of 12 December 2011 on the reuse of Commission documents
                    (2011/833/EU), the ESCO classification can be downloaded, used, reproduced and reused for any purpose and by
                    any interested party free of charge. It may be linked with existing taxonomies or classifications for
                    supplementing and mapping purposes. Any use is subject to the following conditions:

                    1) The use of ESCO shall be acknowledged by publishing the statement below:

                    - For services, tools and applications integrating totally or partially ESCO: "This service uses the ESCO
                      classification of the European Commission."
                    - For other documents such as studies, analysis or reports making use of ESCO: "This publication uses the ESCO
                      classification of the European Commission."

                    2) Any modified or adapted version of ESCO must be clearly indicated as such.

                    Please, be aware that it cannot be guaranteed that the information provided on the ESCO website or in the
                    downloaded files is accurate, up-to-date or complete. The same applies to the quality of translated terms
                    within the classification. The Commission shall not be liable for any consequence stemming from the use,
                    reuse or deployment of the ESCO

                    3) The user agrees that the information submitted in the form below may be used for purposes indicated in the
                    section 2-a.
                    """,
                ),
                (
                    "Disclaimer",
                    """
                    Although we carefully check linked content, we cannot accept liability for external websites. The respective
                    operators are responsible for the content of linked pages.
                    """,
                ),
            ],
            "footnote": "Last updated: March 2024. Update this timestamp whenever you modify the legal content.",
        },
    }

    selected_content = content[lang_label]
    st.write(selected_content["intro"])
    render_sections(selected_content["sections"])
    st.caption(selected_content["footnote"])


if __name__ == "__main__":
    main()
