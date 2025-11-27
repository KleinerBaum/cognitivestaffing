"""Helpers for selecting available OpenAI model identifiers at runtime."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Sequence, Set

from openai import OpenAI

from config import models as model_config

PREF_ENV = "COGNITIVE_PREFERRED_MODEL"
FB_ENV = "COGNITIVE_MODEL_FALLBACKS"

DEFAULT_CANDIDATES = [
    model_config.GPT41_MINI,
    model_config.GPT51_MINI,
    model_config.GPT51_NANO,
]


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
        target = model_config.normalise_model_name(candidate) or candidate
        if target not in available:
            continue
        if target not in resolved_candidates:
            resolved_candidates.append(target)

    if resolved_candidates:
        return resolved_candidates[0]

    if model_config.GPT41_MINI in available:
        return model_config.GPT41_MINI

    sample = sorted(list(available))[:10]
    raise RuntimeError("No usable model found. Tried: %s; Available sample: %s" % (candidates, sample))
