"""Confidence tier utilities for extracted profile fields."""

from __future__ import annotations

from enum import StrEnum
from typing import Final


class ConfidenceTier(StrEnum):
    """Classification of how confident the system is in a field value."""

    RULE_STRONG = "rule_strong"
    AI_ASSISTED = "ai_assisted"


#: Default tier for AI extracted fields.
DEFAULT_AI_TIER: Final[ConfidenceTier] = ConfidenceTier.AI_ASSISTED

#: Tier used when a rule match with a locked field is present.
RULE_LOCK_TIER: Final[ConfidenceTier] = ConfidenceTier.RULE_STRONG
