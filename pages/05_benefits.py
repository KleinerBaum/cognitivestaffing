from __future__ import annotations

from constants.keys import ProfilePaths

from .base import WizardPage


PAGE = WizardPage(
    key="benefits",
    label=("Vergütung & Benefits", "Compensation & benefits"),
    panel_header=("Vergütung", "Compensation"),
    panel_subheader=("Gehalt & Zusatzleistungen", "Salary & perks"),
    panel_intro_variants=(
        (
            "Lege Gehaltsrahmen, Bonusmodell und Benefits transparent fest.",
            "Set a clear salary range, bonus model, and benefit package.",
        ),
        (
            "Strukturierte Vergütungsdaten verbessern Marktplatz-Matching, Benchmarks und Angebotsunterlagen.",
            "Structured compensation data improves marketplace matching, benchmarking, and offer collateral.",
        ),
        (
            "Sag offen, was ihr zahlt und womit ihr Kandidat:innen begeistert.",
            "Be upfront about pay and the perks that make candidates excited.",
        ),
    ),
    required_fields=(),
    summary_fields=(
        ProfilePaths.COMPENSATION_SALARY_PROVIDED,
        ProfilePaths.COMPENSATION_SALARY_MIN,
        ProfilePaths.COMPENSATION_SALARY_MAX,
        ProfilePaths.COMPENSATION_CURRENCY,
        ProfilePaths.COMPENSATION_PERIOD,
        ProfilePaths.COMPENSATION_VARIABLE_PAY,
        ProfilePaths.COMPENSATION_BONUS_PERCENTAGE,
        ProfilePaths.COMPENSATION_COMMISSION_STRUCTURE,
        ProfilePaths.COMPENSATION_EQUITY_OFFERED,
        ProfilePaths.COMPENSATION_BENEFITS,
        ProfilePaths.EMPLOYMENT_JOB_TYPE,
        ProfilePaths.EMPLOYMENT_WORK_POLICY,
        ProfilePaths.EMPLOYMENT_WORK_SCHEDULE,
        ProfilePaths.EMPLOYMENT_CONTRACT_TYPE,
        ProfilePaths.EMPLOYMENT_CONTRACT_END,
        ProfilePaths.EMPLOYMENT_REMOTE_PERCENTAGE,
        ProfilePaths.EMPLOYMENT_TRAVEL_REQUIRED,
        ProfilePaths.EMPLOYMENT_TRAVEL_SHARE,
        ProfilePaths.EMPLOYMENT_TRAVEL_REGION_SCOPE,
        ProfilePaths.EMPLOYMENT_TRAVEL_REGIONS,
        ProfilePaths.EMPLOYMENT_TRAVEL_CONTINENTS,
        ProfilePaths.EMPLOYMENT_TRAVEL_DETAILS,
        ProfilePaths.EMPLOYMENT_OVERTIME_EXPECTED,
        ProfilePaths.EMPLOYMENT_SHIFT_WORK,
        ProfilePaths.EMPLOYMENT_RELOCATION_SUPPORT,
        ProfilePaths.EMPLOYMENT_RELOCATION_DETAILS,
        ProfilePaths.EMPLOYMENT_VISA_SPONSORSHIP,
        ProfilePaths.EMPLOYMENT_SECURITY_CLEARANCE_REQUIRED,
    ),
    allow_skip=True,
)
