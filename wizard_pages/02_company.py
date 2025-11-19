from __future__ import annotations

from .base import WizardPage


_REQUIRED_FIELDS: tuple[str, ...] = (
    "company.name",
    "company.contact_email",
    "location.primary_city",
)
_SUMMARY_FIELDS: tuple[str, ...] = (
    "company.name",
    "company.legal_name",
    "company.brand_name",
    "company.tagline",
    "company.industry",
    "company.industries",
    "company.size",
    "company.website",
    "company.mission",
    "company.hq_location",
    "company.locations",
    "company.culture",
    "company.values",
    "company.brand_keywords",
    "company.contact_name",
    "company.contact_email",
    "company.contact_phone",
    "company.logo_url",
    "company.brand_color",
    "company.claim",
    "company.benefits",
)


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
    required_fields=_REQUIRED_FIELDS,
    summary_fields=_SUMMARY_FIELDS,
    allow_skip=False,
)
