from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Collection, Mapping, MutableMapping, Sequence, cast

from openai import BadRequestError
import streamlit as st

from constants.keys import StateKeys
from state.autosave import persist_session_snapshot
from utils.i18n import tr
import wizard.metadata as wizard_metadata
from wizard import step_registry
from wizard.navigation.keys import WizardSessionKeys
from wizard.navigation_types import StepRenderer, WizardContext
from wizard.types import LocalizedText
from wizard.validation import (
    is_value_present,
    resolve_missing_required_fields,
    validate_required_field_inputs,
)
from wizard_pages import WizardPage

logger = logging.getLogger(__name__)

_CONFIG_ERROR_TYPES: tuple[type[Exception], ...] = (
    AttributeError,
    ImportError,
    KeyError,
)


def _resolve_step_error_messages(page: WizardPage, error: Exception) -> LocalizedText:
    """Return a localized error tuple tailored to the failure cause."""

    label_de = page.label_for("de")
    label_en = page.label_for("en")
    if isinstance(error, BadRequestError):
        return (
            (
                "Die KI konnte für den Schritt „{label}“ kein Ergebnis erzeugen. "
                "Du kannst es erneut versuchen oder die Felder manuell ausfüllen."
            ).format(label=label_de),
            (
                "The AI could not generate a result for the “{label}” step. "
                "You can try again or fill the fields in manually."
            ).format(label=label_en),
        )

    if isinstance(error, _CONFIG_ERROR_TYPES):
        return (
            (
                "Für den Schritt „{label}“ fehlen Konfigurationsdaten (z. B. Hilfetexte). "
                "Bitte aktualisiere die Anwendung und fülle die Felder manuell, falls nötig."
            ).format(label=label_de),
            (
                "Configuration data for the “{label}” step is missing (e.g., help text). "
                "Please update the app and fill the fields manually if needed."
            ).format(label=label_en),
        )

    return (
        (
            "Beim Rendern des Schritts „{label}“ ist ein Fehler aufgetreten. "
            "Bitte bearbeite die Felder manuell oder versuche es erneut."
        ).format(label=label_de),
        ("We couldn't render the “{label}” step. Please edit the fields manually or try again.").format(label=label_en),
    )


@dataclass(frozen=True)
class PageProgressSnapshot:
    """Represents the completion ratio for a single wizard page."""

    page: WizardPage
    section_index: int
    total_fields: int
    missing_fields: int
    completion_ratio: float


class NavigationController:
    """Manage wizard navigation state and progress outside the UI layer."""

    def __init__(
        self,
        *,
        pages: Sequence[WizardPage],
        renderers: Mapping[str, StepRenderer],
        context: WizardContext,
        value_resolver: Callable[[Mapping[str, object], str, object | None], object | None],
        required_field_validators: Mapping[str, Callable[[str | None], tuple[str | None, LocalizedText | None]]],
        validated_fields: Collection[str],
        wizard_id: str = "default",
        query_params: MutableMapping[str, object] | None = None,
        session_state: MutableMapping[str, object] | None = None,
    ) -> None:
        self._all_pages: list[WizardPage] = list(pages)
        self._pages: list[WizardPage] = list(pages)
        self._page_map: dict[str, WizardPage] = {page.key: page for page in pages}
        self._renderers: dict[str, StepRenderer] = dict(renderers)
        self._context = context
        self._resolve_value = value_resolver
        self._required_field_validators = required_field_validators
        self._validated_fields = set(validated_fields)
        self._query_params = cast(MutableMapping[str, object], query_params or st.query_params)
        self._session_state = cast(MutableMapping[str, object], session_state or st.session_state)
        self._wizard_id = wizard_id
        self._session_keys = WizardSessionKeys(wizard_id=wizard_id)
        self._use_legacy_state = wizard_id == "default"
        self._local_state: dict[str, object] | None = None
        self._pending_validation_errors: dict[str, LocalizedText] = {}
        self._refresh_active_pages()
        self.ensure_state_defaults()

    @property
    def pages(self) -> Sequence[WizardPage]:
        self._refresh_active_pages()
        return tuple(self._pages)

    @property
    def context(self) -> WizardContext:
        return self._context

    @property
    def pending_validation_errors(self) -> dict[str, LocalizedText]:
        return self._pending_validation_errors

    @property
    def state(self) -> dict[str, object]:
        try:
            raw_state = self._session_state[self._session_keys.navigation_state]
        except KeyError:
            if self._use_legacy_state:
                raw_state = self._session_state.get("wizard")
                if isinstance(raw_state, dict):
                    self._store_wizard_state(raw_state)
                    return raw_state
                if isinstance(raw_state, Mapping):
                    legacy_coerced = dict(raw_state)
                    self._store_wizard_state(legacy_coerced)
                    return legacy_coerced
            if self._local_state is None:
                self._local_state = {}
            return self._local_state
        if isinstance(raw_state, dict):
            self._local_state = raw_state
            return raw_state
        if isinstance(raw_state, Mapping):
            coerced: dict[str, object] = dict(raw_state)
            if not self._store_wizard_state(coerced):
                self._local_state = coerced
                return coerced
            return coerced
        self._local_state = {}
        return self._local_state

    def _store_wizard_state(self, state: dict[str, object]) -> bool:
        """Persist ``state`` inside ``st.session_state`` when possible."""

        try:
            self._session_state[self._session_keys.navigation_state] = state
            if self._use_legacy_state:
                self._session_state["wizard"] = state
            self._local_state = state
            return True
        except Exception:
            storage = getattr(self._session_state, "_new_session_state", None)
            if isinstance(storage, dict):
                storage[self._session_keys.navigation_state] = state
                if self._use_legacy_state:
                    storage["wizard"] = state
                self._local_state = state
                return True
        return False

    def ensure_state_defaults(self) -> None:
        self._refresh_active_pages()
        state = self.state
        if "current_step" not in state:
            state["current_step"] = self._pages[0].key

    def bootstrap_session_state(self) -> None:
        self._refresh_active_pages()
        state = self.state
        if "current_step" not in state or not isinstance(state.get("current_step"), str):
            state["current_step"] = self._pages[0].key
        already_ready = bool(self._session_state.get(StateKeys.WIZARD_SESSION_READY))
        if already_ready:
            return
        self.sync_with_query_params()
        self._session_state[StateKeys.WIZARD_SESSION_READY] = True

    def bootstrap(self) -> None:
        self.bootstrap_session_state()
        self.update_section_progress()
        self.apply_pending_incomplete_jump()

    def sync_with_query_params(self) -> None:
        self._refresh_active_pages()
        active_keys = tuple(page.key for page in self._pages)
        query_params = self._query_params
        step_values = list(query_params.get_all("step")) if hasattr(query_params, "get_all") else []
        step_param = step_values[0] if step_values else None
        if step_param and step_param in self._page_map:
            desired = step_param
        elif step_param:
            desired = step_registry.resolve_nearest_active_step_key(step_param, active_keys) or self._pages[0].key
        else:
            current = self.state.get("current_step")
            desired = current if isinstance(current, str) and current in self._page_map else self._pages[0].key
        self.state["current_step"] = desired
        self._query_params["step"] = desired

    def ensure_current_is_valid(self) -> None:
        self._refresh_active_pages()
        current = self.state.get("current_step")
        if not isinstance(current, str) or current not in self._page_map:
            fallback = self._resolve_nearest_active_key(current)
            self.state["current_step"] = fallback
            self._query_params["step"] = fallback

    def navigate(self, target_key: str, *, mark_current_complete: bool = False, skipped: bool = False) -> None:
        """Navigate to ``target_key`` and trigger a rerun."""

        self._refresh_active_pages()
        if target_key not in self._page_map:
            return
        current_key = self.state.get("current_step")
        if mark_current_complete and isinstance(current_key, str):
            self.mark_step_completed(current_key, skipped=skipped)

        self._session_state.pop(StateKeys.PENDING_INCOMPLETE_JUMP, None)
        self.set_current_step(target_key)
        self._session_state["_wizard_scroll_to_top"] = True
        st.rerun()

    def get_current_step_key(self) -> str:
        self._refresh_active_pages()
        current = self.state.get("current_step")
        if isinstance(current, str) and current in self._page_map:
            return current
        fallback = self._resolve_nearest_active_key(current)
        self.state["current_step"] = fallback
        return fallback

    def next_key(self, page: WizardPage) -> str | None:
        self._refresh_active_pages()
        if page.next_step_id is not None:
            resolved = page.next_step_id(self._context, self._session_state)
            if isinstance(resolved, str) and resolved:
                if resolved == page.key:
                    logger.warning("Next-step resolver returned current key '%s'", resolved)
                elif resolved in self._page_map:
                    return resolved
                else:
                    logger.warning("Next-step resolver returned unknown key '%s'", resolved)
        index = self._pages.index(page)
        for candidate in self._pages[index + 1 :]:
            return candidate.key
        return None

    def previous_key(self, page: WizardPage) -> str | None:
        self._refresh_active_pages()
        index = self._pages.index(page)
        if index == 0:
            return None
        return self._pages[index - 1].key

    def set_current_step(self, target_key: str) -> None:
        self.state["current_step"] = target_key
        self._query_params["step"] = target_key
        persist_session_snapshot()

    def mark_step_completed(self, step_key: str, *, skipped: bool) -> None:
        completed = self.state.get("completed_steps")
        if isinstance(completed, list):
            if step_key not in completed:
                completed.append(step_key)
        else:
            self.state["completed_steps"] = [step_key]

        if skipped:
            skipped_steps = self.state.get("skipped_steps")
            if isinstance(skipped_steps, list):
                if step_key not in skipped_steps:
                    skipped_steps.append(step_key)
            else:
                self.state["skipped_steps"] = [step_key]
        persist_session_snapshot()

    def apply_pending_incomplete_jump(self) -> None:
        if not self._session_state.pop(StateKeys.PENDING_INCOMPLETE_JUMP, False):
            return
        first_incomplete = self._session_state.get(StateKeys.FIRST_INCOMPLETE_SECTION)
        if not isinstance(first_incomplete, int):
            return
        target_key = self.resolve_step_key_for_legacy_index(first_incomplete)
        if target_key is None:
            return
        self.set_current_step(target_key)
        self._session_state["_wizard_scroll_to_top"] = True

    def resolve_step_key_for_legacy_index(self, index: int) -> str | None:
        for page in self._pages:
            renderer = self._renderers.get(page.key)
            if renderer is not None and renderer.legacy_index == index:
                return page.key
        return None

    def update_section_progress(self) -> tuple[int | None, list[int]]:
        """Refresh progress trackers using shared wizard metadata."""

        missing_fields = list(dict.fromkeys(wizard_metadata.get_missing_critical_fields()))
        sections_with_missing: set[int] = set()
        for field in missing_fields:
            sections_with_missing.add(wizard_metadata.resolve_section_for_field(field))

        first_incomplete: int | None = None
        for section in wizard_metadata.CRITICAL_SECTION_ORDER:
            if section in sections_with_missing:
                first_incomplete = section
                break

        if first_incomplete is None and sections_with_missing:
            first_incomplete = min(sections_with_missing)

        if first_incomplete is None:
            completed_sections = list(wizard_metadata.CRITICAL_SECTION_ORDER)
        else:
            completed_sections = [
                section
                for section in wizard_metadata.CRITICAL_SECTION_ORDER
                if section < first_incomplete and section not in sections_with_missing
            ]

        self._session_state[StateKeys.EXTRACTION_MISSING] = missing_fields
        self._session_state[StateKeys.FIRST_INCOMPLETE_SECTION] = first_incomplete
        self._session_state[StateKeys.COMPLETED_SECTIONS] = completed_sections
        return first_incomplete, completed_sections

    def resolve_missing_required_fields(
        self,
        page: WizardPage,
        *,
        validator: Callable[[Sequence[str]], dict[str, LocalizedText]] | None = None,
    ) -> list[str]:
        missing, errors = resolve_missing_required_fields(
            page,
            required_field_validators=self._required_field_validators,
            validated_fields=self._validated_fields,
            value_resolver=self._resolve_value,
            session_state=self._session_state,
            validator=validator,
        )
        self._pending_validation_errors = errors
        return missing

    def validate_required_field_inputs(self, fields: Sequence[str]) -> dict[str, LocalizedText]:
        return validate_required_field_inputs(
            fields,
            required_field_validators=self._required_field_validators,
            value_resolver=self._resolve_value,
            session_state=self._session_state,
        )

    def build_progress_snapshots(self) -> list[PageProgressSnapshot]:
        """Return per-page completion stats for diagnostics and tests."""

        self._refresh_active_pages()
        raw_completed = self.state.get("completed_steps")
        completed_steps: set[str]
        if isinstance(raw_completed, Collection):
            completed_steps = {step for step in raw_completed if isinstance(step, str)}
        else:
            completed_steps = set()
        profile = self._get_profile()
        snapshots: list[PageProgressSnapshot] = []
        for page in self._pages:
            renderer = self._renderers.get(page.key)
            if renderer is None:
                continue
            fields = wizard_metadata.PAGE_PROGRESS_FIELDS.get(page.key, ())
            missing_fields = self._missing_fields_for_paths(
                fields,
                profile=profile,
                completed_steps=completed_steps,
            )
            total = len(fields)
            missing_count = len(missing_fields)
            ratio = self._calculate_completion_ratio(
                total=total,
                missing=missing_count,
                page_key=page.key,
                completed_steps=completed_steps,
            )
            snapshots.append(
                PageProgressSnapshot(
                    page=page,
                    section_index=renderer.legacy_index,
                    total_fields=total,
                    missing_fields=missing_count,
                    completion_ratio=ratio,
                )
            )
        return snapshots

    @staticmethod
    def _calculate_completion_ratio(
        *,
        total: int,
        missing: int,
        page_key: str,
        completed_steps: Collection[str],
    ) -> float:
        if total == 0:
            return 1.0 if page_key in completed_steps else 0.0
        ratio = 1.0 - (missing / total)
        return max(0.0, min(1.0, ratio))

    def _missing_fields_for_paths(
        self,
        fields: Sequence[str],
        *,
        profile: Mapping[str, object] | None = None,
        completed_steps: Collection[str] | None = None,
    ) -> list[str]:
        if not fields:
            return []
        context_raw = profile or (self._session_state.get(StateKeys.PROFILE, {}) or {})
        context: Mapping[str, object] = context_raw if isinstance(context_raw, Mapping) else {}
        completed_lookup = set(completed_steps or [])
        missing: list[str] = []
        for field in fields:
            if field.startswith(wizard_metadata.VIRTUAL_PAGE_FIELD_PREFIX):
                page_key = field[len(wizard_metadata.VIRTUAL_PAGE_FIELD_PREFIX) :]
                if page_key and page_key not in completed_lookup:
                    missing.append(field)
                continue
            value = self._session_state.get(field)
            if not is_value_present(value):
                value = self._resolve_value(context, field, None)
            if not is_value_present(value):
                missing.append(field)
        return missing

    def _get_profile(self) -> Mapping[str, object]:
        raw_profile = self._session_state.get(StateKeys.PROFILE)
        return raw_profile if isinstance(raw_profile, Mapping) else {}

    def _resolve_active_pages(self) -> list[WizardPage]:
        profile = self._get_profile()
        active_keys = step_registry.resolve_active_step_keys(profile, self._session_state)
        registry_keys = set(step_registry.step_keys())
        page_map = {page.key: page for page in self._all_pages}
        ordered: list[WizardPage] = [page_map[key] for key in active_keys if key in page_map]
        ordered_keys = {page.key for page in ordered}
        for page in self._all_pages:
            if page.key not in registry_keys and page.key not in ordered_keys:
                ordered.append(page)
                ordered_keys.add(page.key)
        if not ordered:
            ordered = list(self._all_pages)
        return ordered

    def _refresh_active_pages(self) -> None:
        ordered = self._resolve_active_pages()
        if [page.key for page in ordered] != [page.key for page in self._pages]:
            self._pages = ordered
            self._page_map = {page.key: page for page in ordered}

    def _resolve_nearest_active_key(self, current: object) -> str:
        active_keys = tuple(page.key for page in self._pages)
        key = current if isinstance(current, str) else ""
        return step_registry.resolve_nearest_active_step_key(key, active_keys) or self._pages[0].key

    def handle_step_exception(self, page: WizardPage, error: Exception) -> None:
        logger.warning("Failed to render wizard step '%s'", page.key, exc_info=error)
        from wizard._logic import _render_localized_error

        message_de, message_en = _resolve_step_error_messages(page, error)
        _render_localized_error(message_de, message_en, error)

    def render_step(self, page: WizardPage) -> None:
        renderer = self._renderers.get(page.key)
        if renderer is None:
            st.warning(tr("Schritt nicht verfügbar.", "Step not available."))
            return

        st.session_state[StateKeys.STEP] = renderer.legacy_index
        try:
            renderer.callback(self._context)
        except Exception as error:  # pragma: no cover - guarded at router level
            self.handle_step_exception(page, error)


__all__ = [
    "BadRequestError",
    "NavigationController",
    "PageProgressSnapshot",
]
