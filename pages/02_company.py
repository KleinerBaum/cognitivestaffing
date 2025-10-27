from __future__ import annotations

from .base import WizardPage


PAGE = WizardPage(
    key="company",
    label=("Unternehmen", "Company"),
    panel_header=("Unternehmensdaten", "Company details"),
    panel_subheader=("Kontakt & Standort", "Contact & location"),
    panel_intro_variants=(
        (
            "Füge Name, Branche und Kontakt ein, damit Abstimmungen funktionieren.",
            "Add name, industry, and contact details to keep stakeholders aligned.",
        ),
        (
            "Diese Angaben steuern Branding, Ansprechpartner und Benchmarks.",
            "These inputs influence branding, contacts, and benchmarks.",
        ),
    ),
    required_fields=(
        "company.name",
        "company.contact_name",
        "company.contact_email",
        "company.contact_phone",
        "location.country",
    ),
    summary_fields=(
        "company.name",
        "company.industry",
        "company.size",
        "location.primary_city",
        "location.country",
    ),
    allow_skip=False,
)
