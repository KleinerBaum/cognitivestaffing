"""Helpers for selecting available OpenAI model identifiers at runtime."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Sequence, Set

from openai import OpenAI

PREF_ENV = "COGNITIVE_PREFERRED_MODEL"
FB_ENV = "COGNITIVE_MODEL_FALLBACKS"

DEFAULT_CANDIDATES = [
    "gpt-4o-mini",
    "o3-mini",
    "o3",
    "o4-mini",
    "gpt-4o",
    "gpt-4",
]

ALIASES = {
    "gpt-5.1-mini": "gpt-4o-mini",
    "gpt-5.1-mini-latest": "gpt-4o-mini",
    "gpt-5.1": "gpt-4o",
    "gpt-5.1-latest": "gpt-4o",
    "gpt-5.1-nano": "gpt-4o-mini",
    "gpt-5.1-nano-latest": "gpt-4o-mini",
}


@lru_cache(maxsize=1)
def _available_models(client: OpenAI) -> Set[str]:
    return {model.id for model in client.models.list()}


def pick_model(client: OpenAI, extra_candidates: Sequence[str] | None = None) -> str:
    candidates: list[str] = []
    preferred = os.getenv(PREF_ENV)
    if preferred:
        candidates.append(preferred.strip())
    fallbacks = os.getenv(FB_ENV)
    if fallbacks:
        candidates.extend(candidate.strip() for candidate in fallbacks.split(",") if candidate.strip())
    if extra_candidates:
        candidates.extend(list(extra_candidates))
    candidates.extend(DEFAULT_CANDIDATES)

    available = _available_models(client)
    resolved_candidates: list[str] = []
    for candidate in candidates:
        target = ALIASES.get(candidate, candidate)
        if target not in available:
            continue
        if target not in resolved_candidates:
            resolved_candidates.append(target)

    if resolved_candidates:
        return resolved_candidates[0]

    if "gpt-4o" in available:
        return "gpt-4o"

    sample = sorted(list(available))[:10]
    raise RuntimeError("No usable model found. Tried: %s; Available sample: %s" % (candidates, sample))
