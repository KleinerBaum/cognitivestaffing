"""Shared regular expression patterns used across normalization and heuristics."""

from __future__ import annotations

import re

__all__ = [
    "GENDER_SUFFIX_INLINE_RE",
    "GENDER_SUFFIX_TRAILING_RE",
]


# Matches gender suffixes appended to job titles such as "(m/w/d)" or
# "(f/m/x)". The inline variant keeps the optional punctuation prefix so the
# caller can remove both segments.
GENDER_SUFFIX_INLINE_RE = re.compile(
    r"(?P<prefix>\s*[-–—:,/|]*)?(?P<suffix>\((?:[mwfd]\s*/\s*){2}[mwfd]\)|all\s+genders)",
    re.IGNORECASE,
)

# Finds gender suffixes at the end of a line so trailing markers like
# "Junior Developer (m/w/d)" can be stripped cleanly.
GENDER_SUFFIX_TRAILING_RE = re.compile(
    r"(?:\((?:[mwfd]\s*/\s*){2}[mwfd]\)|all\s+genders)\s*$",
    re.IGNORECASE,
)
