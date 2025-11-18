from __future__ import annotations

import html
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Collection, Iterable, Mapping, Sequence, Final

from pydantic import ValidationError
import streamlit as st
from streamlit.errors import StreamlitAPIException

from constants.keys import ProfilePaths, StateKeys
from pages import WizardPage
from utils.i18n import tr
from wizard._logic import get_in, _render_localized_error
from wizard.followups import followup_has_response
from wizard.layout import (
    NavigationButtonState,
    NavigationDirection,
    NavigationState,
    render_navigation_controls,
)
from wizard.metadata import (
    CRITICAL_SECTION_ORDER,
    PAGE_FOLLOWUP_PREFIXES,
    PAGE_PROGRESS_FIELDS,
    VIRTUAL_PAGE_FIELD_PREFIX,
    get_missing_critical_fields,
    resolve_section_for_field,
)
from wizard.company_validators import persist_contact_email, persist_primary_city

# ``wizard.metadata`` stays lightweight so this router can depend on shared
# progress data without importing the Streamlit-heavy ``wizard.flow`` module.

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


@dataclass(frozen=True)
class WizardContext:
    """Context passed to step renderer callables."""

    schema: Mapping[str, object]
    critical_fields: Sequence[str]


@dataclass(frozen=True)
class StepRenderer:
    """Callable wrapper with legacy index mapping for Streamlit state sync."""

    callback: Callable[[WizardContext], None]
    legacy_index: int


@dataclass(frozen=True)
class _PageProgressSnapshot:
    """Represents the completion ratio for a single wizard page."""

    page: WizardPage
    section_index: int
    total_fields: int
    missing_fields: int
    completion_ratio: float


_COLLECTED_STYLE = """
<style>
.wizard-collected-panel {
    border-radius: 1rem;
    background: var(--surface-0, rgba(241, 245, 249, 0.65));
    border: 1px solid var(--border-subtle, rgba(148, 163, 184, 0.35));
    padding: 1rem 1.25rem;
    margin-bottom: 1.25rem;
    box-shadow: 0 12px 28px rgba(15, 23, 42, 0.18);
    color: var(--text-strong, #0f172a);
}
.wizard-collected-panel h4 {
    margin: 0 0 0.35rem 0;
    font-weight: 600;
    letter-spacing: 0.01em;
    color: var(--text-strong, #0f172a);
}
.wizard-collected-panel p {
    margin: 0 0 0.75rem 0;
    color: var(--text-soft, rgba(15, 23, 42, 0.7));
    line-height: 1.55;
}
.wizard-chip-list {
    display: flex;
    flex-wrap: wrap;
    gap: 0.45rem;
}
.wizard-chip {
    display: inline-flex;
    align-items: center;
    border-radius: 999px;
    padding: 0.25rem 0.75rem;
    background: var(--interactive-surface, rgba(59, 130, 246, 0.12));
    color: var(--text-strong, #0f172a);
    border: 1px solid var(--border-subtle, rgba(148, 163, 184, 0.35));
    font-size: 0.85rem;
    font-weight: 600;
}
.wizard-chip.is-empty {
    background: transparent;
    border-style: dashed;
}
@media (max-width: 640px) {
    .wizard-collected-panel {
        padding: 0.85rem 1rem;
    }
}
</style>
"""

logger = logging.getLogger(__name__)

_SUMMARY_LABELS: tuple[tuple[str, str], ...] = (
    ("Onboarding", "Onboarding"),
    ("Unternehmen", "Company"),
    ("Team & Kontext", "Team & context"),
    ("Rolle & Aufgaben", "Role & tasks"),
    ("Skills & Anforderungen", "Skills & requirements"),
    ("Leistungen & Benefits", "Rewards & Benefits"),
    ("Prozess", "Process"),
    ("Summary", "Summary"),
)

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
)


_NAVIGATION_STYLE = """
<style>
.wizard-nav-marker + div[data-testid="stHorizontalBlock"] {
    display: flex;
    gap: var(--space-sm, 0.6rem);
    align-items: stretch;
    margin: 1.2rem 0 0.65rem;
}

.wizard-nav-marker
    + div[data-testid="stHorizontalBlock"]
    > div[data-testid="column"] {
    flex: 1 1 0;
}

.wizard-nav-marker
    + div[data-testid="stHorizontalBlock"]
    .wizard-nav-next button {
    min-height: 3rem;
    font-size: 1.02rem;
    font-weight: 650;
    transition:
        box-shadow var(--transition-base, 0.18s ease-out),
        transform var(--transition-base, 0.18s ease-out),
        background-color var(--transition-base, 0.18s ease-out);
    will-change: transform, box-shadow;
}

.wizard-nav-marker
    + div[data-testid="stHorizontalBlock"]
    button {
    width: 100%;
    border-radius: 14px;
}

.wizard-nav-marker
    + div[data-testid="stHorizontalBlock"]
    .wizard-nav-next button[kind="primary"] {
    box-shadow: 0 16px 32px rgba(37, 58, 95, 0.2);
}

.wizard-nav-marker
    + div[data-testid="stHorizontalBlock"]
    .wizard-nav-next--enabled button[kind="primary"] {
    animation: wizardNavPulse 1.2s ease-out 1;
}

.wizard-nav-marker
    + div[data-testid="stHorizontalBlock"]
    .wizard-nav-next button[kind="primary"]:hover:not(:disabled) {
    box-shadow: 0 20px 40px rgba(37, 58, 95, 0.26);
    transform: translateY(-1px);
}

.wizard-nav-marker
    + div[data-testid="stHorizontalBlock"]
    .wizard-nav-next button:disabled {
    box-shadow: none;
    opacity: 0.55;
}

.wizard-nav-marker
    + div[data-testid="stHorizontalBlock"]
    .wizard-nav-next--disabled button {
    transform: none;
}

.wizard-nav-hint {
    margin-top: 0.35rem;
    color: var(--text-soft, rgba(15, 23, 42, 0.7));
    font-size: 0.9rem;
}

@media (max-width: 768px) {
    .wizard-nav-marker + div[data-testid="stHorizontalBlock"] {
        flex-direction: column;
    }

    .wizard-nav-marker
        + div[data-testid="stHorizontalBlock"]
        > div[data-testid="column"] {
        width: 100%;
    }

    .wizard-nav-marker
        + div[data-testid="stHorizontalBlock"]
        .wizard-nav-next button {
        position: sticky;
        bottom: 1rem;
        z-index: 10;
        box-shadow: 0 16px 32px rgba(15, 23, 42, 0.22);
    }

    .wizard-nav-marker
        + div[data-testid="stHorizontalBlock"]
        button {
        min-height: 3rem;
    }
}

@keyframes wizardNavPulse {
    0% {
        box-shadow: 0 0 0 0 rgba(59, 130, 246, 0.0);
        transform: scale(0.995);
    }
    40% {
        box-shadow: 0 0 0 6px rgba(59, 130, 246, 0.15);
        transform: scale(1.01);
    }
    100% {
        box-shadow: 0 16px 32px rgba(37, 58, 95, 0.2);
        transform: scale(1);
    }
}
</style>
"""


_PROGRESS_STYLE = """
<style>
    .wizard-progress-wrapper {
        margin: 0.75rem 0 1.25rem;
        display: flex;
        gap: clamp(0.6rem, 1.25vw, 1rem);
        align-items: stretch;
        justify-content: center;
    }

    .wizard-progress-bubble {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 0.35rem;
        text-align: center;
    }

    .wizard-progress-bubble button {
        width: 3rem;
        height: 3rem;
        border-radius: 50%;
        border: 2px solid transparent;
        color: #0f172a;
        font-weight: 700;
        font-size: 1rem;
        transition: transform 0.18s ease, box-shadow 0.18s ease;
    }

    .wizard-progress-bubble.is-current button {
        transform: translateY(-2px);
        box-shadow: 0 12px 28px rgba(15, 23, 42, 0.18);
        border-color: rgba(37, 99, 235, 0.65);
    }

    .wizard-progress-caption {
        font-size: 0.85rem;
        line-height: 1.25;
        color: var(--text-soft, rgba(15, 23, 42, 0.72));
        max-width: 8rem;
    }

    .wizard-progress-meta {
        font-size: 0.75rem;
        color: var(--text-faint, rgba(100, 116, 139, 0.95));
    }

    @media (max-width: 960px) {
        .wizard-progress-wrapper {
            flex-wrap: wrap;
            gap: 0.75rem;
        }

        .wizard-progress-bubble button {
            width: 2.75rem;
            height: 2.75rem;
        }
    }
</style>
"""


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
        self._resolve_value: Callable[[Mapping[str, object], str, object | None], object | None] = value_resolver
        self._local_state: dict[str, object] | None = None
        self._pending_validation_errors: dict[str, LocalizedText] = {}
        self._ensure_state_defaults()
        st.session_state[StateKeys.WIZARD_STEP_COUNT] = len(self._pages)
        self._bootstrap_session_state()
        self._update_section_progress()
        self._apply_pending_incomplete_jump()

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
        """Navigate to ``target_key`` and trigger a rerun."""

        if target_key not in self._page_map:
            return

        current_key = self._state.get("current_step")
        if mark_current_complete and isinstance(current_key, str):
            self._mark_step_completed(current_key, skipped=skipped)

        st.session_state.pop(StateKeys.PENDING_INCOMPLETE_JUMP, None)
        self._set_current_step(target_key)
        st.session_state["_wizard_scroll_to_top"] = True
        st.rerun()

    def run(self) -> None:
        """Render the current step with harmonised navigation controls."""

        st.markdown(_COLLECTED_STYLE + _NAVIGATION_STYLE, unsafe_allow_html=True)
        self._update_section_progress()
        self._ensure_current_is_valid()
        current_key = self._get_current_step_key()
        page = self._page_map[current_key]
        renderer = self._renderers.get(page.key)
        if renderer is None:
            st.warning(tr("Schritt nicht verfügbar.", "Step not available."))
            return

        st.session_state[StateKeys.STEP] = renderer.legacy_index
        last_rendered = self._state.get("_last_rendered_step")
        if last_rendered != current_key:
            st.session_state["_wizard_scroll_to_top"] = True
            self._state["_last_rendered_step"] = current_key
        self._maybe_scroll_to_top()
        self._render_progress_tracker(current_key)
        self._render_collected_panel(page)
        lang = st.session_state.get("lang", "de")
        summary_labels = [tr(de, en, lang=lang) for de, en in _SUMMARY_LABELS]
        st.session_state["_wizard_step_summary"] = (renderer.legacy_index, summary_labels)
        try:
            renderer.callback(self._context)
        except (RerunException, StopException):  # pragma: no cover - Streamlit control flow
            raise
        except _STEP_RECOVERABLE_ERRORS as error:
            self._handle_step_exception(page, error)
        except Exception as error:  # pragma: no cover - defensive guard
            self._handle_step_exception(page, error)
        missing = self._missing_required_fields(page)
        self._render_navigation(page, missing)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    @property
    def _state(self) -> dict[str, object]:
        try:
            raw_state = st.session_state["wizard"]
        except KeyError:
            if self._local_state is None:
                self._local_state = {}
            return self._local_state
        if isinstance(raw_state, dict):
            self._local_state = raw_state
            return raw_state
        coerced: dict[str, object] = dict(raw_state)
        if not self._store_wizard_state(coerced):
            self._local_state = coerced
            return coerced
        return coerced

    def _store_wizard_state(self, state: dict[str, object]) -> bool:
        """Persist ``state`` inside ``st.session_state`` when possible."""

        try:
            st.session_state["wizard"] = state
            self._local_state = state
            return True
        except Exception:
            storage = getattr(st.session_state, "_new_session_state", None)
            if isinstance(storage, dict):
                storage["wizard"] = state
                self._local_state = state
                return True
        return False

    def _get_current_step_key(self) -> str:
        current = self._state.get("current_step")
        if isinstance(current, str) and current in self._page_map:
            return current
        fallback = self._pages[0].key
        self._state["current_step"] = fallback
        return fallback

    def _ensure_state_defaults(self) -> None:
        state = self._state
        if "current_step" not in state:
            state["current_step"] = self._pages[0].key

    def _handle_step_exception(self, page: WizardPage, error: Exception) -> None:
        label_de = page.label_for("de")
        label_en = page.label_for("en")
        logger.warning("Failed to render wizard step '%s'", page.key, exc_info=error)
        _render_localized_error(
            f"Beim Rendern des Schritts „{label_de}“ ist ein Fehler aufgetreten. "
            "Bitte bearbeite die Felder manuell oder versuche es erneut.",
            f"We couldn't render the “{label_en}” step. Please edit the fields manually or try again.",
            error,
        )

    def _bootstrap_session_state(self) -> None:
        state = self._state
        if "current_step" not in state or not isinstance(state.get("current_step"), str):
            state["current_step"] = self._pages[0].key
        already_ready = bool(st.session_state.get(StateKeys.WIZARD_SESSION_READY))
        if already_ready:
            return
        self._sync_with_query_params()
        st.session_state[StateKeys.WIZARD_SESSION_READY] = True

    def _sync_with_query_params(self) -> None:
        query_params = st.query_params
        step_values = list(query_params.get_all("step"))
        step_param = step_values[0] if step_values else None
        if step_param and step_param in self._page_map:
            desired = step_param
        else:
            current = self._state.get("current_step")
            desired = current if isinstance(current, str) and current in self._page_map else self._pages[0].key
        self._state["current_step"] = desired
        query_params["step"] = desired

    def _ensure_current_is_valid(self) -> None:
        current = self._state.get("current_step")
        if not isinstance(current, str) or current not in self._page_map:
            self._state["current_step"] = self._pages[0].key

    def _next_key(self, page: WizardPage) -> str | None:
        index = self._pages.index(page)
        for candidate in self._pages[index + 1 :]:
            return candidate.key
        return None

    def _prev_key(self, page: WizardPage) -> str | None:
        index = self._pages.index(page)
        if index == 0:
            return None
        return self._pages[index - 1].key

    def _missing_required_fields(self, page: WizardPage) -> list[str]:
        profile = st.session_state.get(StateKeys.PROFILE, {}) or {}
        missing: list[str] = []
        required_fields = tuple(page.required_fields or ())
        if required_fields:
            validation_errors = self._validate_required_field_inputs(required_fields)
            if validation_errors:
                self._pending_validation_errors = validation_errors
            else:
                self._pending_validation_errors = {}
            for field in required_fields:
                if field in _PROFILE_VALIDATED_FIELDS:
                    value = None
                else:
                    value = st.session_state.get(field)
                if not self._is_value_present(value):
                    value = self._resolve_value(profile, field, None)
                if not self._is_value_present(value):
                    missing.append(field)
            if validation_errors:
                for field in validation_errors:
                    if field not in missing:
                        missing.append(field)
        else:
            self._pending_validation_errors = {}
        inline_missing = self._missing_inline_followups(page, profile)
        if inline_missing:
            missing.extend(inline_missing)
        if not missing:
            return []
        # Preserve order while removing duplicates
        return list(dict.fromkeys(missing))

    def _missing_inline_followups(self, page: WizardPage, profile: Mapping[str, object]) -> list[str]:
        prefixes = PAGE_FOLLOWUP_PREFIXES.get(page.key, ())
        if not prefixes:
            return []
        followups = st.session_state.get(StateKeys.FOLLOWUPS)
        if not isinstance(followups, list):
            return []
        missing: list[str] = []
        for question in followups:
            if not isinstance(question, Mapping):
                continue
            field = question.get("field")
            if not isinstance(field, str) or not field:
                continue
            if not any(field.startswith(prefix) for prefix in prefixes):
                continue
            if question.get("priority") != "critical":
                continue
            value = st.session_state.get(field)
            if not followup_has_response(value):
                value = get_in(profile, field, None)
            if not followup_has_response(value):
                missing.append(field)
        return missing

    @staticmethod
    def _is_value_present(value: object | None) -> bool:
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        if isinstance(value, (list, tuple, set)):
            return any(WizardRouter._is_value_present(item) for item in value)
        if isinstance(value, Mapping):
            return any(WizardRouter._is_value_present(item) for item in value.values())
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        return True

    def _render_collected_panel(self, page: WizardPage) -> None:
        lang = st.session_state.get("lang", "de")
        header = page.header_for(lang)
        subheader = page.subheader_for(lang)
        context = st.session_state.get(StateKeys.PROFILE, {}) or {}
        intro = self._resolve_intro(page, lang, context)
        values = list(self._collect_summary_values(page.summary_fields, context))
        with st.container():
            st.markdown("<div class='wizard-collected-panel'>", unsafe_allow_html=True)
            st.markdown(f"<h4>{html.escape(header)}</h4>", unsafe_allow_html=True)
            st.markdown(f"<p><em>{html.escape(subheader)}</em></p>", unsafe_allow_html=True)
            if intro:
                st.caption(intro)
            if values:
                chips = "".join(f"<span class='wizard-chip'>{html.escape(item)}</span>" for item in values)
                st.markdown(f"<div class='wizard-chip-list'>{chips}</div>", unsafe_allow_html=True)
            else:
                st.caption(tr("Noch keine Angaben erfasst.", "No data captured yet."))
            st.markdown("</div>", unsafe_allow_html=True)

    def _resolve_intro(self, page: WizardPage, lang: str, context: Mapping[str, object]) -> str:
        for variant in page.intro_variants_for(lang):
            try:
                return variant.format(**self._flatten_context(context))
            except Exception:
                continue
        return ""

    def _flatten_context(self, context: Mapping[str, object]) -> Mapping[str, str]:
        flat: dict[str, str] = {}
        if not isinstance(context, Mapping):
            return flat
        company = context.get("company")
        if isinstance(company, Mapping):
            if company.get("name"):
                flat["company_name"] = str(company.get("name"))
            if company.get("industry"):
                flat["company_industry"] = str(company.get("industry"))
        position = context.get("position")
        if isinstance(position, Mapping):
            if position.get("job_title"):
                flat["job_title"] = str(position.get("job_title"))
        location = context.get("location")
        if isinstance(location, Mapping):
            if location.get("primary_city"):
                flat["primary_city"] = str(location.get("primary_city"))
            if location.get("country"):
                flat["country"] = str(location.get("country"))
        return flat

    def _collect_summary_values(self, fields: Iterable[str], context: Mapping[str, object]) -> Iterable[str]:
        for field in fields:
            value = self._resolve_value(context, field, None)
            if isinstance(value, str) and value.strip():
                yield value.strip()
            elif isinstance(value, (list, tuple, set)):
                cleaned = [str(item).strip() for item in value if isinstance(item, str) and item.strip()]
                if cleaned:
                    for entry in cleaned:
                        yield entry
            elif value not in (None, "", []):
                yield str(value)

    def _render_navigation(self, page: WizardPage, missing: Sequence[str]) -> None:
        prev_key = self._prev_key(page)
        next_key = self._next_key(page)
        missing_tuple = tuple(missing)

        def _nav_callback(
            target: str,
            *,
            mark_complete: bool = False,
            skipped: bool = False,
        ) -> Callable[[], None]:
            def _run() -> None:
                self.navigate(target, mark_current_complete=mark_complete, skipped=skipped)

            return _run

        previous_button = (
            NavigationButtonState(
                direction=NavigationDirection.PREVIOUS,
                label=("◀ Zurück", "◀ Back"),
                target_key=prev_key,
                on_click=_nav_callback(prev_key),
            )
            if prev_key
            else None
        )

        if next_key:
            next_hint: LocalizedText | None = None
            if missing_tuple:
                next_hint = (
                    "Pflichtfelder fehlen",
                    "Complete required fields first",
                )

            next_button = NavigationButtonState(
                direction=NavigationDirection.NEXT,
                label=("Weiter ▶", "Next ▶"),
                target_key=next_key,
                enabled=not missing_tuple,
                primary=True,
                hint=next_hint,
                on_click=_nav_callback(next_key, mark_complete=True),
            )
        else:
            next_button = None

        skip_button = None
        if page.allow_skip and next_key:
            skip_button = NavigationButtonState(
                direction=NavigationDirection.SKIP,
                label=("Überspringen", "Skip"),
                target_key=next_key,
                on_click=_nav_callback(next_key, mark_complete=True, skipped=True),
            )

        nav_state = NavigationState(
            current_key=page.key,
            missing_fields=missing_tuple,
            previous=previous_button,
            next=next_button,
            skip=skip_button,
        )
        render_navigation_controls(nav_state)
        self._render_validation_warnings()

    def _maybe_scroll_to_top(self) -> None:
        if not st.session_state.pop("_wizard_scroll_to_top", False):
            return
        st.markdown(
            """
            <script>
            (function() {
                const root = window;
                const target = root.document.querySelector('section.main');
                const scrollToTop = () => {
                    if (!target) {
                        root.scrollTo({ top: 0, behavior: 'smooth' });
                        return;
                    }
                    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    setTimeout(() => {
                        target.setAttribute('tabindex', '-1');
                        target.focus({ preventScroll: true });
                    }, 180);
                };
                if ('requestAnimationFrame' in root) {
                    root.requestAnimationFrame(scrollToTop);
                } else {
                    scrollToTop();
                }
            })();
            </script>
            """,
            unsafe_allow_html=True,
        )

    def _update_section_progress(self) -> tuple[int | None, list[int]]:
        """Refresh progress trackers using shared wizard metadata."""

        missing_fields = list(dict.fromkeys(get_missing_critical_fields()))
        sections_with_missing: set[int] = set()
        for field in missing_fields:
            sections_with_missing.add(resolve_section_for_field(field))

        first_incomplete: int | None = None
        for section in CRITICAL_SECTION_ORDER:
            if section in sections_with_missing:
                first_incomplete = section
                break

        if first_incomplete is None and sections_with_missing:
            first_incomplete = min(sections_with_missing)

        if first_incomplete is None:
            completed_sections = list(CRITICAL_SECTION_ORDER)
        else:
            completed_sections = [
                section
                for section in CRITICAL_SECTION_ORDER
                if section < first_incomplete and section not in sections_with_missing
            ]

        st.session_state[StateKeys.EXTRACTION_MISSING] = missing_fields
        st.session_state[StateKeys.FIRST_INCOMPLETE_SECTION] = first_incomplete
        st.session_state[StateKeys.COMPLETED_SECTIONS] = completed_sections
        return first_incomplete, completed_sections

    def _validate_required_field_inputs(self, fields: Sequence[str]) -> dict[str, LocalizedText]:
        """Re-run profile-bound validators for ``fields`` using widget state."""

        errors: dict[str, LocalizedText] = {}
        for field in fields:
            validator = _REQUIRED_FIELD_VALIDATORS.get(field)
            if validator is None:
                continue
            raw_value_obj = st.session_state.get(field)
            raw_value = raw_value_obj if isinstance(raw_value_obj, str) else None
            _, error = validator(raw_value)
            if error:
                errors[field] = error
        return errors

    def _render_validation_warnings(self) -> None:
        """Show bilingual warnings for inline validator failures."""

        if not self._pending_validation_errors:
            return
        messages = list(dict.fromkeys(self._pending_validation_errors.values()))
        if not messages:
            return
        lang = st.session_state.get("lang", "de")
        combined = "\n\n".join(tr(de, en, lang=lang) for de, en in messages)
        if combined.strip():
            st.warning(combined)

    def _apply_pending_incomplete_jump(self) -> None:
        if not st.session_state.pop(StateKeys.PENDING_INCOMPLETE_JUMP, False):
            return
        first_incomplete = st.session_state.get(StateKeys.FIRST_INCOMPLETE_SECTION)
        if not isinstance(first_incomplete, int):
            return
        target_key = self._resolve_step_key_for_legacy_index(first_incomplete)
        if target_key is None:
            return
        self._set_current_step(target_key)
        st.session_state["_wizard_scroll_to_top"] = True

    def _resolve_step_key_for_legacy_index(self, index: int) -> str | None:
        for page in self._pages:
            renderer = self._renderers.get(page.key)
            if renderer is not None and renderer.legacy_index == index:
                return page.key
        return None

    def _set_current_step(self, target_key: str) -> None:
        self._state["current_step"] = target_key
        st.query_params["step"] = target_key

    def _mark_step_completed(self, step_key: str, *, skipped: bool) -> None:
        completed = self._state.get("completed_steps")
        if isinstance(completed, list):
            if step_key not in completed:
                completed.append(step_key)
        else:
            self._state["completed_steps"] = [step_key]

        if skipped:
            skipped_steps = self._state.get("skipped_steps")
            if isinstance(skipped_steps, list):
                if step_key not in skipped_steps:
                    skipped_steps.append(step_key)
            else:
                self._state["skipped_steps"] = [step_key]

    # ------------------------------------------------------------------
    # Progress tracker helpers
    # ------------------------------------------------------------------
    def _render_progress_tracker(self, current_key: str) -> None:
        if not self._pages:
            return

        st.markdown(_PROGRESS_STYLE, unsafe_allow_html=True)
        snapshots = self._build_progress_snapshots()
        snapshot_lookup = {snapshot.page.key: snapshot for snapshot in snapshots}
        lang = st.session_state.get("lang", "de")
        wrapper = st.container()
        with wrapper:
            st.markdown("<div class='wizard-progress-wrapper'>", unsafe_allow_html=True)
            columns = st.columns(len(self._pages), gap="small")
            style_chunks: list[str] = []
            for position, (col, page) in enumerate(zip(columns, self._pages), start=1):
                snapshot = snapshot_lookup.get(page.key)
                if snapshot is None:
                    continue
                completion_ratio = snapshot.completion_ratio
                bubble_id = f"wizard-progress-{page.key}"
                color = self._interpolate_color(completion_ratio)
                style_chunks.append(
                    (
                        f"#{bubble_id} button {{\n"
                        f"    background: {color};\n"
                        "    color: var(--text-strong, #0f172a);\n"
                        "}\n"
                        f"#{bubble_id} button:hover {{\n"
                        "    filter: brightness(1.05);\n"
                        "}"
                    )
                )
                label = page.label_for(lang)
                caption = page.subheader_for(lang)
                percent_label = f"{int(round(completion_ratio * 100))}%"
                wrapper_class = "wizard-progress-bubble"
                if page.key == current_key:
                    wrapper_class += " is-current"
                col.markdown(
                    f"<div class='{wrapper_class}' id='{bubble_id}'>",
                    unsafe_allow_html=True,
                )
                clicked = col.button(
                    str(position),
                    key=f"wizard_progress_{page.key}",
                    help=caption,
                )
                col.markdown("</div>", unsafe_allow_html=True)
                col.markdown(
                    f"<div class='wizard-progress-meta'>{percent_label}</div>",
                    unsafe_allow_html=True,
                )
                col.markdown(
                    f"<div class='wizard-progress-caption'>{html.escape(label)}</div>",
                    unsafe_allow_html=True,
                )
                if clicked and page.key != current_key:
                    self.navigate(page.key)
            if style_chunks:
                st.markdown(
                    "<style>" + "\n\n".join(style_chunks) + "</style>",
                    unsafe_allow_html=True,
                )
            st.markdown("</div>", unsafe_allow_html=True)

    def _build_progress_snapshots(self) -> list[_PageProgressSnapshot]:
        """Return per-page completion stats for the progress tracker."""

        raw_completed = self._state.get("completed_steps")
        completed_steps: set[str]
        if isinstance(raw_completed, Collection):
            completed_steps = {step for step in raw_completed if isinstance(step, str)}
        else:
            completed_steps = set()
        profile = st.session_state.get(StateKeys.PROFILE, {}) or {}
        snapshots: list[_PageProgressSnapshot] = []
        for page in self._pages:
            renderer = self._renderers.get(page.key)
            if renderer is None:
                continue
            fields = PAGE_PROGRESS_FIELDS.get(page.key, ())
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
                _PageProgressSnapshot(
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

    @staticmethod
    def _interpolate_color(ratio: float) -> str:
        base = (191, 219, 254)  # #bfdbfe
        peak = (30, 64, 175)  # #1e40af
        r = int(base[0] + (peak[0] - base[0]) * ratio)
        g = int(base[1] + (peak[1] - base[1]) * ratio)
        b = int(base[2] + (peak[2] - base[2]) * ratio)
        return f"#{r:02x}{g:02x}{b:02x}"

    def _missing_fields_for_paths(
        self,
        fields: Sequence[str],
        *,
        profile: Mapping[str, object] | None = None,
        completed_steps: Collection[str] | None = None,
    ) -> list[str]:
        if not fields:
            return []
        context = profile or (st.session_state.get(StateKeys.PROFILE, {}) or {})
        completed_lookup = set(completed_steps or [])
        missing: list[str] = []
        for field in fields:
            if field.startswith(VIRTUAL_PAGE_FIELD_PREFIX):
                page_key = field[len(VIRTUAL_PAGE_FIELD_PREFIX) :]
                if page_key and page_key not in completed_lookup:
                    missing.append(field)
                continue
            value = st.session_state.get(field)
            if not self._is_value_present(value):
                value = self._resolve_value(context, field, None)
            if not self._is_value_present(value):
                missing.append(field)
        return missing
