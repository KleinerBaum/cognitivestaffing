from __future__ import annotations

from constants.keys import ProfilePaths

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
        ProfilePaths.COMPANY_NAME,
        ProfilePaths.COMPANY_CONTACT_NAME,
        ProfilePaths.COMPANY_CONTACT_EMAIL,
        ProfilePaths.COMPANY_CONTACT_PHONE,
        ProfilePaths.LOCATION_COUNTRY,
    ),
    summary_fields=(
        ProfilePaths.COMPANY_NAME,
        ProfilePaths.COMPANY_BRAND_NAME,
        ProfilePaths.COMPANY_BRAND_KEYWORDS,
        ProfilePaths.COMPANY_BRAND_COLOR,
        ProfilePaths.COMPANY_CLAIM,
        ProfilePaths.COMPANY_INDUSTRY,
        ProfilePaths.COMPANY_SIZE,
        ProfilePaths.COMPANY_HQ_LOCATION,
        ProfilePaths.COMPANY_WEBSITE,
        ProfilePaths.COMPANY_MISSION,
        ProfilePaths.COMPANY_CULTURE,
        ProfilePaths.COMPANY_CONTACT_NAME,
        ProfilePaths.COMPANY_CONTACT_EMAIL,
        ProfilePaths.COMPANY_CONTACT_PHONE,
        ProfilePaths.COMPANY_LOGO_URL,
        ProfilePaths.LOCATION_PRIMARY_CITY,
        ProfilePaths.LOCATION_COUNTRY,
        ProfilePaths.LOCATION_ONSITE_RATIO,
    ),
    allow_skip=False,
)
