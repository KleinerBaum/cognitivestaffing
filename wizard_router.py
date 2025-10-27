from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Mapping, Sequence

import html
import streamlit as st

from constants.keys import StateKeys
from pages import WizardPage
from utils.i18n import tr


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


_COLLECTED_STYLE = """
<style>
.wizard-collected-panel {
    border-radius: 1rem;
    background: var(--surface-0, rgba(241, 245, 249, 0.65));
    border: 1px solid var(--border-subtle, rgba(148, 163, 184, 0.35));
    padding: 1rem 1.25rem;
    margin-bottom: 1.25rem;
}
.wizard-collected-panel h4 {
    margin: 0 0 0.35rem 0;
}
.wizard-collected-panel p {
    margin: 0 0 0.75rem 0;
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
    background: var(--surface-accent, rgba(59, 130, 246, 0.08));
    color: var(--text-strong, #0f172a);
    font-size: 0.85rem;
    font-weight: 600;
}
</style>
"""

_NAVIGATION_STYLE = """
<style>
.wizard-nav-marker + div[data-testid="stHorizontalBlock"] {
    display: flex;
    gap: 0.75rem;
    align-items: stretch;
    margin: 1.1rem 0 0.5rem;
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
}

.wizard-nav-marker
    + div[data-testid="stHorizontalBlock"]
    button {
    width: 100%;
}

.wizard-nav-marker
    + div[data-testid="stHorizontalBlock"]
    .wizard-nav-next button[kind="primary"] {
    box-shadow: 0 8px 20px rgba(37, 99, 235, 0.25);
}

.wizard-nav-marker
    + div[data-testid="stHorizontalBlock"]
    .wizard-nav-next button[kind="primary"]:hover:not(:disabled) {
    box-shadow: 0 10px 24px rgba(37, 99, 235, 0.3);
}

.wizard-nav-marker
    + div[data-testid="stHorizontalBlock"]
    .wizard-nav-next button:disabled {
    box-shadow: none;
    opacity: 0.7;
}

.wizard-nav-hint {
    margin-top: 0.35rem;
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
    }

    .wizard-nav-marker
        + div[data-testid="stHorizontalBlock"]
        button {
        min-height: 3rem;
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
        self._pages = list(pages)
        self._page_map = {page.key: page for page in pages}
        self._renderers = dict(renderers)
        self._context = context
        self._resolve_value = value_resolver
        self._ensure_state_defaults()
        self._sync_with_query_params()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def run(self) -> None:
        """Render the current step with harmonised navigation controls."""

        st.markdown(_COLLECTED_STYLE + _NAVIGATION_STYLE, unsafe_allow_html=True)
        self._ensure_current_is_valid()
        current_key = self._state["current_step"]
        page = self._page_map[current_key]
        renderer = self._renderers.get(page.key)
        if renderer is None:
            st.warning(tr("Schritt nicht verfügbar.", "Step not available."))
            return

        st.session_state[StateKeys.STEP] = renderer.legacy_index
        missing = self._missing_required_fields(page)
        self._maybe_scroll_to_top()
        self._render_collected_panel(page)
        renderer.callback(self._context)
        self._render_navigation(page, missing)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    @property
    def _state(self) -> dict[str, object]:
        return st.session_state.setdefault("wizard", {})  # type: ignore[return-value]

    def _ensure_state_defaults(self) -> None:
        state = self._state
        if "current_step" not in state:
            state["current_step"] = self._pages[0].key

    def _sync_with_query_params(self) -> None:
        params = st.experimental_get_query_params()
        step_param = params.get("step", [None])[0]
        if step_param and step_param in self._page_map:
            self._state["current_step"] = step_param
        else:
            params.pop("step", None)
            params["step"] = [self._state["current_step"]]
        st.experimental_set_query_params(**params)

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
        if not page.required_fields:
            return []
        profile = st.session_state.get(StateKeys.PROFILE, {}) or {}
        missing: list[str] = []
        for field in page.required_fields:
            value = st.session_state.get(field)
            if not self._is_value_present(value):
                value = self._resolve_value(profile, field, None)
            if not self._is_value_present(value):
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
        st.markdown("<div class='wizard-nav-marker'></div>", unsafe_allow_html=True)
        cols = st.columns((1.1, 1.1, 1), gap="small")
        if prev_key:
            if cols[0].button(
                "◀ " + tr("Zurück", "Back"),
                key=f"wizard_prev_{page.key}",
                use_container_width=True,
            ):
                self._navigate_to(prev_key)
        else:
            cols[0].write("")

        next_disabled = bool(missing)
        if next_disabled:
            with cols[1]:
                st.markdown("<div class='wizard-nav-next'>", unsafe_allow_html=True)
                st.button(
                    tr("Weiter", "Next") + " ▶",
                    key=f"wizard_next_{page.key}",
                    type="primary",
                    disabled=True,
                    use_container_width=True,
                )
                st.markdown("</div>", unsafe_allow_html=True)
            missing_label = tr("Pflichtfelder fehlen", "Complete required fields first")
            cols[1].caption(missing_label)
        elif next_key:
            with cols[1]:
                st.markdown("<div class='wizard-nav-next'>", unsafe_allow_html=True)
                if st.button(
                    tr("Weiter", "Next") + " ▶",
                    key=f"wizard_next_{page.key}",
                    type="primary",
                    use_container_width=True,
                ):
                    self._navigate_to(next_key)
                st.markdown("</div>", unsafe_allow_html=True)
        else:
            cols[1].write("")

        if page.allow_skip and next_key:
            with cols[2]:
                if st.button(
                    tr("Überspringen", "Skip"),
                    key=f"wizard_skip_{page.key}",
                    use_container_width=True,
                ):
                    self._navigate_to(next_key)
        else:
            cols[2].write("")

    def _navigate_to(self, target_key: str) -> None:
        self._state["current_step"] = target_key
        params = st.experimental_get_query_params()
        params["step"] = [target_key]
        st.experimental_set_query_params(**params)
        st.session_state["_wizard_scroll_to_top"] = True
        st.rerun()

    def _maybe_scroll_to_top(self) -> None:
        if not st.session_state.pop("_wizard_scroll_to_top", False):
            return
        st.markdown(
            """
            <script>
            (function() {
                const root = window;
                const target = root.document.querySelector('section.main');
                root.scrollTo({ top: 0, behavior: 'smooth' });
                if (target) {
                    target.setAttribute('tabindex', '-1');
                    target.focus({ preventScroll: true });
                }
            })();
            </script>
            """,
            unsafe_allow_html=True,
        )
