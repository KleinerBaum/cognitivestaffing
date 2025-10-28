from __future__ import annotations

from constants.keys import ProfilePaths
from core.schema import is_wizard_schema_enabled

from .base import WizardPage


if is_wizard_schema_enabled():
    _REQUIRED_FIELDS = ("company.name",)
    _SUMMARY_FIELDS = (
        "company.name",
        "company.legal_name",
        "company.tagline",
        "company.mission",
        "company.headquarters",
        "company.locations",
        "company.industries",
        "company.website",
        "company.values",
    )
else:
    _REQUIRED_FIELDS = tuple(
        field.value
        for field in (
            ProfilePaths.COMPANY_NAME,
            ProfilePaths.COMPANY_CONTACT_NAME,
            ProfilePaths.COMPANY_CONTACT_EMAIL,
            ProfilePaths.COMPANY_CONTACT_PHONE,
            ProfilePaths.LOCATION_COUNTRY,
        )
    )
    _SUMMARY_FIELDS = tuple(
        field.value
        for field in (
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
        )
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
