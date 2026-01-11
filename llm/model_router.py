"""Helpers for selecting available OpenAI model identifiers at runtime."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Mapping, Sequence, Set

from openai import OpenAI

from config import models as model_config

PREF_ENV = "COGNITIVE_PREFERRED_MODEL"
FB_ENV = "COGNITIVE_MODEL_FALLBACKS"

DEFAULT_CANDIDATES = [
    model_config.GPT41_MINI,
    model_config.GPT51_MINI,
    model_config.GPT51_NANO,
]

TIER_FALLBACKS: Mapping[str, Sequence[str]] = {
    "FAST": (
        model_config.GPT51_NANO,
        model_config.GPT41_NANO,
        model_config.GPT4O_MINI,
    ),
    "QUALITY": (
        model_config.GPT51_MINI,
        model_config.GPT41_MINI,
        model_config.GPT4O,
    ),
    "LONG_CONTEXT": (
        model_config.GPT41_NANO,
        model_config.GPT41_MINI,
    ),
}


@dataclass
class _ModelCacheEntry:
    fetched_at: float
    models: Set[str]


_MODEL_CACHE_TTL_SECONDS = 60 * 60
_MODEL_CACHE: dict[str, _ModelCacheEntry] = {}


def _model_cache_key(client: OpenAI) -> str:
    base_url = str(getattr(client, "base_url", "") or "")
    organization = str(getattr(client, "organization", "") or "")
    project = str(getattr(client, "project", "") or "")
    return "|".join([base_url, organization, project])


def _available_models(client: OpenAI) -> Set[str]:
    cache_key = _model_cache_key(client)
    cached = _MODEL_CACHE.get(cache_key)
    now = time.time()
    if cached and now - cached.fetched_at < _MODEL_CACHE_TTL_SECONDS:
        return cached.models
    models = {model.id for model in client.models.list()}
    _MODEL_CACHE[cache_key] = _ModelCacheEntry(fetched_at=now, models=models)
    return models


def _clear_model_cache() -> None:
    _MODEL_CACHE.clear()


_available_models.cache_clear = _clear_model_cache  # type: ignore[attr-defined]


def _resolve_candidates(
    client: OpenAI,
    candidates: Sequence[str],
) -> str:
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


def _env_candidates(extra_candidates: Sequence[str] | None = None) -> list[str]:
    candidates: list[str] = []
    preferred = os.getenv(PREF_ENV)
    if preferred:
        candidates.append(preferred.strip())
    fallbacks = os.getenv(FB_ENV)
    if fallbacks:
        candidates.extend(candidate.strip() for candidate in fallbacks.split(",") if candidate.strip())
    if extra_candidates:
        candidates.extend(list(extra_candidates))
    return candidates


def pick_model(client: OpenAI, extra_candidates: Sequence[str] | None = None) -> str:
    candidates = _env_candidates(extra_candidates)
    candidates.extend(DEFAULT_CANDIDATES)
    return _resolve_candidates(client, candidates)


def pick_model_for_tier(
    client: OpenAI,
    tier: str,
    extra_candidates: Sequence[str] | None = None,
) -> str:
    tier_candidates = list(TIER_FALLBACKS.get(tier, ()))
    candidates = _env_candidates(extra_candidates)
    candidates.extend(tier_candidates)
    if not candidates:
        candidates.extend(DEFAULT_CANDIDATES)
    return _resolve_candidates(client, candidates)
