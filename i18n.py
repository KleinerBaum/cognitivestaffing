"""Core translation utilities for Cognitive Needs."""

from __future__ import annotations

STR = {
    "de": {
        "suggestion_group_llm": "LLM-Vorschläge",
        "suggestion_group_esco_skill": "ESCO Pflicht-Skills • Praxis",
        "suggestion_group_esco_knowledge": "ESCO Pflicht-Skills • Wissen",
        "suggestion_group_esco_competence": "ESCO Pflicht-Skills • Kompetenzen",
        "suggestion_group_esco_tools": "ESCO Pflicht-Skills • Tools & Tech",
        "suggestion_group_esco_certificates": "ESCO Pflicht-Skills • Zertifikate",
        "suggestion_group_esco_missing_skill": "Fehlende ESCO-Skills",
        "suggestion_group_esco_missing_knowledge": "Fehlendes ESCO-Wissen",
        "suggestion_group_esco_missing_competence": "Fehlende ESCO-Kompetenzen",
        "suggestion_group_esco_missing_tools": "Fehlende ESCO-Tools",
        "suggestion_group_esco_missing_certificates": "Fehlende ESCO-Zertifikate",
        "role_questions.software_developers.programming_languages": "Welche Programmiersprachen wird die Entwickler:in einsetzen?",
        "role_questions.software_developers.development_methodology": "Welche Entwicklungsmethodik verwendet das Team?",
        "role_questions.sales_professionals.target_markets": "Auf welche Zielmärkte konzentriert sich die Vertriebsrolle?",
        "role_questions.sales_professionals.sales_quota": "Wie lautet die Sales-Quota für diese Position?",
        "role_questions.sales_professionals.campaign_types": "Welche Kampagnentypen verantwortet die Marketing-Person?",
        "role_questions.sales_professionals.digital_marketing_platforms": "Welche digitalen Marketing-Plattformen kommen zum Einsatz?",
        "role_questions.nursing.shift_schedule": "Wie sieht der Schichtplan aus?",
        "role_questions.medical_doctors.board_certification": "Welche Facharzt- oder Board-Zertifizierungen sind erforderlich?",
        "role_questions.medical_doctors.on_call_requirements": "Gibt es Bereitschafts- oder Rufdienste für diese Rolle?",
        "role_questions.teachers.grade_level": "Welche Klassenstufen unterrichtet die Lehrkraft?",
        "role_questions.teachers.teaching_license": "Ist eine Lehrbefähigung erforderlich?",
        "role_questions.designers.design_software_tools": "Welche Design-Software sollte die Person sicher beherrschen?",
        "role_questions.designers.portfolio_url": "Wie lautet die Portfolio-URL?",
        "role_questions.business_managers.project_management_methodologies": "Welche Projektmanagement-Methoden werden genutzt?",
        "role_questions.business_managers.budget_responsibility": "Welche Budgetverantwortung bringt die Rolle mit sich?",
        "role_questions.systems_analysts.machine_learning_frameworks": "Welche Machine-Learning-Frameworks werden benötigt?",
        "role_questions.systems_analysts.data_analysis_tools": "Welche Datenanalyse-Tools werden verwendet?",
        "role_questions.accountants.accounting_software": "Welche Buchhaltungssoftware wird eingesetzt?",
        "role_questions.accountants.professional_certifications": "Welche beruflichen Zertifizierungen werden verlangt?",
        "role_questions.hr.hr_software_tools": "Welche HR-Software-Tools kommen zum Einsatz?",
        "role_questions.hr.recruitment_channels": "Welche Recruiting-Kanäle haben Priorität?",
        "role_questions.civil_engineers.civil_project_types": "Welche Bauprojekte übernimmt die Ingenieur:in?",
        "role_questions.civil_engineers.engineering_software_tools": "Welche Ingenieur-Software ist erforderlich?",
        "role_questions.chefs.cuisine_specialties": "Welche Küchen-Schwerpunkte sollte der/die Chef:in mitbringen?",
    },
    "en": {
        "suggestion_group_llm": "LLM suggestions",
        "suggestion_group_esco_skill": "ESCO essentials • Practical",
        "suggestion_group_esco_knowledge": "ESCO essentials • Knowledge",
        "suggestion_group_esco_competence": "ESCO essentials • Competence",
        "suggestion_group_esco_tools": "ESCO essentials • Tools & Tech",
        "suggestion_group_esco_certificates": "ESCO essentials • Certificates",
        "suggestion_group_esco_missing_skill": "Outstanding ESCO skills",
        "suggestion_group_esco_missing_knowledge": "Outstanding ESCO knowledge",
        "suggestion_group_esco_missing_competence": "Outstanding ESCO competences",
        "suggestion_group_esco_missing_tools": "Outstanding ESCO tools",
        "suggestion_group_esco_missing_certificates": "Outstanding ESCO certificates",
        "role_questions.software_developers.programming_languages": "Which programming languages will the developer use?",
        "role_questions.software_developers.development_methodology": "Which development methodology does the team follow?",
        "role_questions.sales_professionals.target_markets": "Which target markets will the salesperson focus on?",
        "role_questions.sales_professionals.sales_quota": "What is the sales quota for this role?",
        "role_questions.sales_professionals.campaign_types": "What campaign types will the marketer manage?",
        "role_questions.sales_professionals.digital_marketing_platforms": "Which digital marketing platforms are used?",
        "role_questions.nursing.shift_schedule": "What is the shift schedule?",
        "role_questions.medical_doctors.board_certification": "What board certifications are required?",
        "role_questions.medical_doctors.on_call_requirements": "Are there on-call requirements for this role?",
        "role_questions.teachers.grade_level": "Which grade levels will the teacher instruct?",
        "role_questions.teachers.teaching_license": "Is a teaching license required?",
        "role_questions.designers.design_software_tools": "Which design software tools should the designer be proficient in?",
        "role_questions.designers.portfolio_url": "What is the portfolio URL?",
        "role_questions.business_managers.project_management_methodologies": "Which project management methodologies are used?",
        "role_questions.business_managers.budget_responsibility": "What budget responsibility does this role carry?",
        "role_questions.systems_analysts.machine_learning_frameworks": "Which machine learning frameworks are required?",
        "role_questions.systems_analysts.data_analysis_tools": "Which data analysis tools are used?",
        "role_questions.accountants.accounting_software": "Which accounting software is used?",
        "role_questions.accountants.professional_certifications": "Which professional certifications are required?",
        "role_questions.hr.hr_software_tools": "Which HR software tools are used?",
        "role_questions.hr.recruitment_channels": "Which recruitment channels are prioritised?",
        "role_questions.civil_engineers.civil_project_types": "What types of civil projects will the engineer handle?",
        "role_questions.civil_engineers.engineering_software_tools": "Which engineering software tools are required?",
        "role_questions.chefs.cuisine_specialties": "Which cuisine specialities should the chef have?",
    },
}


def t(key: str, lang: str) -> str:
    """Translate ``key`` into the requested ``lang``.

    Args:
        key: Lookup key in the translation dictionary.
        lang: Language code (``"de"`` or ``"en"``).

    Returns:
        The localized string if present, otherwise ``key`` itself.
    """

    return STR.get(lang, {}).get(key, key)
