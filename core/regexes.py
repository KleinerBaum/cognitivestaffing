"""Shared regular expressions for Cognitive Staffing heuristics."""

from __future__ import annotations

import re

CITY_REGEX_IN_PATTERN = re.compile(
    r"(?i)\bsuchen wir (?:ab sofort )?in\s+(?P<city>(?-i:[A-ZÄÖÜ][A-Za-zÄÖÜäöüß'`.-]+(?:\s+[A-ZÄÖÜ][A-Za-zÄÖÜäöüß'`.-]+){0,2}))",
)
"""Regex capturing city names in phrases like 'suchen wir in Düsseldorf'."""

FOOTER_CONTACT_PARSE = re.compile(
    r"""
    IT[-\s]?Leiter:\s*(?P<mgr>[^;,\n]+?)\s*;
    \s*HR[-\s]?Ansprechpartner:?\s*(?P<hr>[^;,\n]+?)\s*;
    (?:\s*E-?Mails?:\s*(?P<emails>[^;\n]+?)\s*;)?
    (?:\s*(?:Telefon|Phone):?\s*(?P<phone>0[\d/ .-]+)[^;\n]*;)?
    (?:\s*(?:Website|Web):?\s*(?P<website>https?://[^\s;]+))?
    """,
    re.IGNORECASE | re.VERBOSE,
)
"""Regex matching Rheinbahn-style footer contact blocks."""
