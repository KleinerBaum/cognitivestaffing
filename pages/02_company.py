from __future__ import annotations

from .base import WizardPage


_REQUIRED_FIELDS: tuple[str, ...] = ("company.name",)
_SUMMARY_FIELDS: tuple[str, ...] = (
    "company.name",
    "company.legal_name",
    "company.tagline",
    "company.mission",
    "company.headquarters",
    "company.locations",
    "company.industries",
    "company.website",
    "company.values",
    "company.logo_url",
    "company.brand_color",
    "company.claim",
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
