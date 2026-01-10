from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable, Mapping, Sequence, Final

from pydantic import ValidationError
import streamlit as st
from streamlit.errors import StreamlitAPIException

from constants.keys import ProfilePaths, StateKeys
from openai_utils.errors import (
    ExternalServiceError,
    LLMResponseFormatError,
    NeedAnalysisPipelineError,
    SchemaValidationError,
)
from utils.i18n import tr
from utils.logging_context import log_context, set_wizard_step
from wizard.company_validators import persist_contact_email, persist_primary_city
from wizard.metadata import (
    PAGE_SECTION_INDEXES,
    field_belongs_to_page,
    get_missing_critical_fields,
    resolve_section_for_field,
)
from wizard.navigation import (
    NavigationController,
    PageProgressSnapshot,
    build_navigation_state,
    inject_navigation_style,
    maybe_scroll_to_top,
    render_navigation,
    render_validation_warnings,
)
from wizard.navigation_types import StepRenderer, WizardContext
from wizard_pages import WizardPage

if TYPE_CHECKING:  # pragma: no cover - typing-only import path
    from streamlit.runtime.scriptrunner import (
        RerunException as StreamlitRerunException,
        StopException as StreamlitStopException,
    )
else:  # pragma: no cover - Streamlit runtime internals are unavailable in unit tests
    try:
        from streamlit.runtime.scriptrunner import (
            RerunException as StreamlitRerunException,
            StopException as StreamlitStopException,
        )
    except Exception:

        class StreamlitRerunException(RuntimeError):
            """Fallback rerun exception when Streamlit internals cannot be imported."""

        class StreamlitStopException(RuntimeError):
            """Fallback stop exception when Streamlit internals cannot be imported."""


RerunException = StreamlitRerunException
StopException = StreamlitStopException

logger = logging.getLogger(__name__)

LocalizedText = tuple[str, str]

_REQUIRED_FIELD_VALIDATORS: Final[dict[str, Callable[[str | None], tuple[str | None, LocalizedText | None]]]] = {
    str(ProfilePaths.COMPANY_CONTACT_EMAIL): persist_contact_email,
    str(ProfilePaths.LOCATION_PRIMARY_CITY): persist_primary_city,
}

_PROFILE_VALIDATED_FIELDS: Final[set[str]] = set(_REQUIRED_FIELD_VALIDATORS)

_STEP_RECOVERABLE_ERRORS: tuple[type[Exception], ...] = (
    StreamlitAPIException,
    ValidationError,
    ValueError,
    NeedAnalysisPipelineError,
    SchemaValidationError,
    LLMResponseFormatError,
    ExternalServiceError,
)


class WizardRouter:
    """Synchronise wizard navigation between query params and Streamlit state."""

    def __init__(
        self,
        *,
        pages: Sequence[WizardPage],
        renderers: Mapping[str, StepRenderer],
        context: WizardContext,
        value_resolver: Callable[[Mapping[str, object], str, object | None], object | None],
    ) -> None:
        self._pages: list[WizardPage] = list(pages)
        self._page_map: dict[str, WizardPage] = {page.key: page for page in pages}
        self._renderers: dict[str, StepRenderer] = dict(renderers)
        self._context: WizardContext = context
        self._controller = NavigationController(
            pages=pages,
            renderers=renderers,
            context=context,
            value_resolver=value_resolver,
            required_field_validators=_REQUIRED_FIELD_VALIDATORS,
            validated_fields=_PROFILE_VALIDATED_FIELDS,
        )
        active_pages = self._controller.pages
        self._summary_labels: tuple[LocalizedText, ...] = tuple(page.label for page in active_pages)
        st.session_state[StateKeys.WIZARD_STEP_COUNT] = len(active_pages)
        already_ready = bool(st.session_state.get(StateKeys.WIZARD_SESSION_READY))
        if not already_ready:
            self._sync_with_query_params()
            st.session_state[StateKeys.WIZARD_SESSION_READY] = True
        self._controller.update_section_progress()
        self._controller.apply_pending_incomplete_jump()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def navigate(
        self,
        target_key: str,
        *,
        mark_current_complete: bool = False,
        skipped: bool = False,
    ) -> None:
        self._controller.navigate(target_key, mark_current_complete=mark_current_complete, skipped=skipped)

    def run(self) -> None:
        """Render the current step with harmonised navigation controls."""

        inject_navigation_style()
        active_pages = self._controller.pages
        self._summary_labels = tuple(page.label for page in active_pages)
        st.session_state[StateKeys.WIZARD_STEP_COUNT] = len(active_pages)
        self._controller.update_section_progress()
        self._controller.ensure_current_is_valid()
        current_key = self._controller.get_current_step_key()
        page = self._page_map[current_key]
        renderer = self._renderers.get(page.key)
        if renderer is None:
            st.warning(tr("Schritt nicht verfügbar.", "Step not available."))
            return

        with log_context(wizard_step=page.key):
            set_wizard_step(page.key)
            logger.info("Entering wizard step %s", page.key)
            st.session_state[StateKeys.STEP] = renderer.legacy_index
            last_rendered = self._state.get("_last_rendered_step")
            if last_rendered != current_key:
                st.session_state["_wizard_scroll_to_top"] = True
                self._state["_last_rendered_step"] = current_key
            maybe_scroll_to_top()
            lang = st.session_state.get("lang", "de")
            summary_labels = [tr(de, en, lang=lang) for de, en in self._summary_labels]
            st.session_state["_wizard_step_summary"] = (renderer.legacy_index, summary_labels)
            try:
                renderer.callback(self._context)
            except (RerunException, StopException):  # pragma: no cover - Streamlit control flow
                raise
            except _STEP_RECOVERABLE_ERRORS as error:
                self._controller.handle_step_exception(page, error)
            except Exception as error:  # pragma: no cover - defensive guard
                self._controller.handle_step_exception(page, error)
            missing = self._missing_required_fields(page)
            nav_state = build_navigation_state(
                page=page,
                missing=missing,
                previous_key=self._controller.previous_key(page),
                next_key=self._controller.next_key(page),
                allow_skip=page.allow_skip,
                navigate_factory=self._build_nav_callback,
            )
            render_validation_warnings(self._controller.pending_validation_errors)
            render_navigation(nav_state)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    @property
    def _state(self) -> dict[str, object]:
        return self._controller.state

    def _build_nav_callback(
        self,
        target: str,
        mark_complete: bool,
        skipped: bool,
    ) -> Callable[[], None]:
        def _run() -> None:
            self.navigate(target, mark_current_complete=mark_complete, skipped=skipped)

        return _run

    def _build_progress_snapshots(self) -> list[PageProgressSnapshot]:
        return self._controller.build_progress_snapshots()

    def _missing_required_fields(self, page: WizardPage) -> list[str]:
        missing = self._controller.resolve_missing_required_fields(page, validator=self._validate_required_field_inputs)
        section_index = PAGE_SECTION_INDEXES.get(page.key)
        if section_index is None:
            return missing

        critical_missing = [
            field
            for field in get_missing_critical_fields(max_section=section_index)
            if resolve_section_for_field(field) == section_index
        ]
        combined = list(dict.fromkeys((*missing, *critical_missing)))
        if not combined:
            return combined

        return [field for field in combined if field_belongs_to_page(field, page.key)]

    def _validate_required_field_inputs(self, fields: Sequence[str]) -> dict[str, LocalizedText]:
        return self._controller.validate_required_field_inputs(fields)

    def _sync_with_query_params(self) -> None:
        self._controller.sync_with_query_params()
