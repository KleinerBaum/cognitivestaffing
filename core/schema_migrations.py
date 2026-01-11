"""Schema migration helpers for :class:`NeedAnalysisProfile` payloads."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from copy import deepcopy
from typing import Any, Callable

from models.need_analysis import CURRENT_SCHEMA_VERSION, NeedAnalysisProfile


logger = logging.getLogger(__name__)


MigrationFunc = Callable[[dict[str, Any]], dict[str, Any]]


def _noop_migration(payload: dict[str, Any]) -> dict[str, Any]:
    """Return payload unchanged for legacy schemas without breaking flow."""

    return payload


def _migrate_v1_to_v2(payload: dict[str, Any]) -> dict[str, Any]:
    """Introduce the ``business_context`` section from legacy fields."""

    company = payload.get("company")
    department = payload.get("department")
    location = payload.get("location")

    if isinstance(payload.get("business_context"), Mapping):
        business_context = dict(payload["business_context"])
    else:
        business_context = {}

    if not str(business_context.get("domain") or "").strip():
        if isinstance(company, Mapping):
            business_context["domain"] = str(company.get("industry") or "").strip()
        else:
            business_context["domain"] = ""

    if not str(business_context.get("org_name") or "").strip():
        if isinstance(company, Mapping):
            business_context["org_name"] = company.get("name")

    if not str(business_context.get("org_unit") or "").strip():
        if isinstance(department, Mapping):
            business_context["org_unit"] = department.get("name")

    if not str(business_context.get("location") or "").strip():
        if isinstance(location, Mapping) and location.get("primary_city"):
            business_context["location"] = location.get("primary_city")
        elif isinstance(company, Mapping):
            business_context["location"] = company.get("hq_location")

    business_context.setdefault("industry_codes", [])
    business_context.setdefault("compliance_flags", [])
    business_context.setdefault("source_confidence", {})

    payload["business_context"] = business_context
    return payload


MIGRATIONS: dict[int, MigrationFunc] = {1: _migrate_v1_to_v2}


def _extract_version(payload: Mapping[str, Any]) -> int:
    """Return the schema version encoded in ``payload`` when present."""

    raw_version = payload.get("schema_version")
    try:
        version = int(raw_version) if raw_version is not None else 1
    except (TypeError, ValueError):
        return 1
    return max(version, 1)


def migrate_profile(profile_dict: Mapping[str, Any] | None) -> dict[str, Any]:
    """Upgrade a serialized profile dict to ``CURRENT_SCHEMA_VERSION``.

    The helper copies ``profile_dict`` to avoid mutating caller-owned data,
    applies stepwise migrations based on the embedded ``schema_version``, and
    fills missing fields using the latest model defaults. When encountering a
    newer version than supported, a ``ValueError`` is raised so callers can
    decide whether to halt or request an application upgrade.
    """

    source: Mapping[str, Any] = profile_dict or {}
    if not isinstance(source, Mapping):
        raise TypeError("profile_dict must be a mapping when provided")

    version = _extract_version(source)
    payload = deepcopy(dict(source))
    payload.pop("schema_version", None)

    if version > CURRENT_SCHEMA_VERSION:
        msg = f"Cannot migrate profile with schema_version={version}; current={CURRENT_SCHEMA_VERSION}"
        raise ValueError(msg)

    if version < CURRENT_SCHEMA_VERSION:
        logger.debug("Migrating NeedAnalysisProfile from v%s to v%s", version, CURRENT_SCHEMA_VERSION)

    while version < CURRENT_SCHEMA_VERSION:
        migrator = MIGRATIONS.get(version, _noop_migration)
        payload = migrator(payload)
        version += 1

    skeleton = NeedAnalysisProfile().model_dump(mode="python")

    def _merge(base: dict[str, Any], updates: Mapping[str, Any]) -> None:
        for key, value in updates.items():
            if isinstance(value, Mapping) and isinstance(base.get(key), dict):
                _merge(base[key], value)
            else:
                base[key] = value

    _merge(skeleton, payload)
    skeleton["schema_version"] = CURRENT_SCHEMA_VERSION
    return skeleton
