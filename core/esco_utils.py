"""Re-export ESCO utility functions within the core package."""

from esco_utils import (
    classify_occupation,
    enrich_skills_with_esco,
    get_essential_skills,
)

__all__ = [
    "classify_occupation",
    "enrich_skills_with_esco",
    "get_essential_skills",
]
