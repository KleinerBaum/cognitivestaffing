from __future__ import annotations

from typing import Iterable

import streamlit as st


_DOMAIN_SUGGESTIONS = {
    "de": [
        "FinTech",
        "HealthTech",
        "E-Commerce",
        "Industrial IoT",
        "B2B SaaS",
    ],
    "en": [
        "FinTech",
        "HealthTech",
        "E-commerce",
        "Industrial IoT",
        "B2B SaaS",
    ],
}

_INDUSTRY_CODE_RULES: list[tuple[Iterable[str], list[str]]] = [
    (("fintech", "banking", "payments"), ["NACE:K64", "NACE:K66"]),
    (("health", "medtech", "healthtech"), ["NACE:Q86", "NACE:C32"]),
    (("e-commerce", "ecommerce", "retail"), ["NACE:G47"]),
    (("logistics", "supply chain", "transport"), ["NACE:H49", "NACE:H52"]),
    (("energy", "renewable", "solar"), ["NACE:D35"]),
    (("manufacturing", "industrial", "iot"), ["NACE:C27", "NACE:C28"]),
    (("software", "saas", "cloud"), ["NACE:J62"]),
]


def domain_suggestion_chips(current_domain: str | None) -> list[str]:
    lang = str(st.session_state.get("lang", "de"))
    options = _DOMAIN_SUGGESTIONS.get(lang, _DOMAIN_SUGGESTIONS["en"])
    domain_value = (current_domain or "").strip()
    if not domain_value:
        return options
    return [option for option in options if option.casefold() != domain_value.casefold()]


@st.cache_data(ttl=3600)
def suggest_esco_or_industry_codes(domain: str) -> list[str]:
    """Return industry code suggestions derived from ``domain``.

    TODO: Replace keyword rules with ESCO/NACE ontology lookup when available.
    """

    normalized = domain.strip().casefold()
    if not normalized:
        return []
    suggestions: list[str] = []
    for keywords, codes in _INDUSTRY_CODE_RULES:
        if any(keyword in normalized for keyword in keywords):
            suggestions.extend(codes)
    return list(dict.fromkeys(suggestions))
