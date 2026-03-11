"""Typed planning context used to align follow-up ranking across services."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PlanContext(BaseModel):
    """Shared context that influences follow-up prioritization."""

    model_config = ConfigDict(extra="ignore")

    role_family: str | None = None
    location: str | None = None
    work_policy: str | None = None
    compliance: tuple[str, ...] = Field(default_factory=tuple)
    hiring_urgency: str | None = None
    risk_signals: tuple[str, ...] = Field(default_factory=tuple)

    @classmethod
    def from_profile_and_session(
        cls,
        profile: Mapping[str, Any],
        session_state: Mapping[str, Any] | None = None,
    ) -> "PlanContext":
        """Build planning context from profile payload and Streamlit session state."""

        session_state = session_state or {}
        role_family = _first_text(
            _get_path(profile, "position.role_family"),
            _get_path(profile, "position.occupation_group"),
            _get_path(profile, "role.department"),
            session_state.get("plan_context.role_family"),
        )
        location = _first_text(
            _get_path(profile, "location.primary_city"),
            _get_path(profile, "location.country"),
            _get_path(profile, "work.location"),
            session_state.get("plan_context.location"),
        )
        work_policy = _first_text(
            _get_path(profile, "employment.work_policy"),
            _get_path(profile, "work.work_policy"),
            session_state.get("plan_context.work_policy"),
        )
        hiring_urgency = _first_text(
            _get_path(profile, "process.recruitment_timeline"),
            _get_path(profile, "constraints.timeline"),
            session_state.get("plan_context.hiring_urgency"),
        )
        compliance = _normalize_text_list(
            _get_path(profile, "business_context.compliance_flags"),
            session_state.get("plan_context.compliance"),
        )
        risk_signals = _normalize_text_list(
            _get_path(profile, "warnings"),
            _get_path(profile, "risk_signals"),
            session_state.get("plan_context.risk_signals"),
        )

        return cls(
            role_family=role_family,
            location=location,
            work_policy=work_policy,
            compliance=compliance,
            hiring_urgency=hiring_urgency,
            risk_signals=risk_signals,
        )


def context_weight_for_field(field_path: str, plan_context: PlanContext | None) -> int:
    """Return a deterministic boost score for a follow-up field."""

    if not field_path:
        return 0
    if plan_context is None:
        return 0

    normalized = field_path.strip().lower()
    weight = 0

    if _matches(normalized, "position.", "role.") and plan_context.role_family:
        weight += 2
    if _matches(normalized, "location.", "work.location") and plan_context.location:
        weight += 2
    if _matches(normalized, "employment.work_policy", "work.work_policy") and plan_context.work_policy:
        weight += 3
    if _matches(normalized, "process.", "constraints.timeline", "selection.") and plan_context.hiring_urgency:
        weight += 2

    compliance_active = bool(plan_context.compliance)
    if compliance_active and _matches(
        normalized,
        "requirements.background_check_required",
        "requirements.reference_check_required",
        "requirements.portfolio_required",
    ):
        weight += 3

    risk_text = " ".join(plan_context.risk_signals).lower()
    if risk_text:
        if "compliance" in risk_text and normalized.startswith("requirements."):
            weight += 2
        if "timeline" in risk_text and _matches(normalized, "process.", "constraints.timeline"):
            weight += 2
        if "location" in risk_text and normalized.startswith("location."):
            weight += 2

    return weight


def _matches(value: str, *prefixes: str) -> bool:
    return any(value.startswith(prefix) for prefix in prefixes)


def _normalize_text_list(*values: Any) -> tuple[str, ...]:
    items: list[str] = []
    for value in values:
        if isinstance(value, (list, tuple, set)):
            iterable = value
        elif value is None:
            iterable = []
        else:
            iterable = [value]
        for item in iterable:
            text = str(item).strip()
            if text and text not in items:
                items.append(text)
    return tuple(items)


def _first_text(*values: Any) -> str | None:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return None


def _get_path(data: Mapping[str, Any], path: str) -> Any:
    current: Any = data
    for part in path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return None
        current = current[part]
    return current


__all__ = ["PlanContext", "context_weight_for_field"]
