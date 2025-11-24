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
    "company.description",
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
    panel_header=("Unternehmen", "Company"),
    panel_subheader=("Profil & Kontakt", "Profile & contact"),
    panel_intro_variants=(
        (
            "Falls nichts erkannt wurde, ergänze Name, Branche und Kontakt – sonst bitte kurz prüfen und bestätigen.",
            "If nothing was detected, add name, industry, and contact details – otherwise just review and confirm.",
        ),
        (
            "Wir haben Felder aus der Anzeige übernommen; passe sie an, wenn der Job-Text unvollständig war.",
            "We pre-filled fields from the job ad; tweak them if the posting was incomplete.",
        ),
    ),
    required_fields=_REQUIRED_FIELDS,
    summary_fields=_SUMMARY_FIELDS,
    allow_skip=False,
)
