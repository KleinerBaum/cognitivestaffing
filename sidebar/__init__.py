from __future__ import annotations

import html
import re
from base64 import b64encode
from dataclasses import dataclass
from datetime import datetime
from collections.abc import Sequence
from functools import partial
from functools import lru_cache
from io import BytesIO
from types import ModuleType
from typing import Any, Callable, Iterable, Mapping
from urllib.parse import urlparse

import streamlit as st

from streamlit.runtime.uploaded_file_manager import UploadedFile

from PIL.Image import Image as PILImage

from constants.keys import ProfilePaths, StateKeys, UIKeys
from core.preview import build_prefilled_sections, preview_value_to_text
from utils.i18n import tr
from utils.llm_state import is_llm_available, llm_disabled_message
from utils.usage import build_usage_markdown, usage_totals

from streamlit.delta_generator import DeltaGenerator
from streamlit.navigation.page import StreamlitPage

# Lazy wizard imports keep the module importable without circular references.
from constants.style_variants import STYLE_VARIANTS, STYLE_VARIANT_ORDER

from ingest.branding import DEFAULT_BRAND_COLOR

from .salary import (
    SalaryFactorEntry,
    build_factor_influence_chart,
    estimate_salary_expectation,
    format_salary_range,
    prepare_salary_factor_entries,
)


LogoRenderable = PILImage | BytesIO


@lru_cache(maxsize=1)
def _wizard_exports() -> tuple[Mapping[str, int], Callable[[], Sequence[str]], ModuleType, Callable[[str, Any], None]]:
    from wizard import FIELD_SECTION_MAP, get_missing_critical_fields, logic, _update_profile

    return FIELD_SECTION_MAP, get_missing_critical_fields, logic, _update_profile


def _wizard_field_section_map() -> Mapping[str, int]:
    field_map, _missing_fn, _logic_module, _update_fn = _wizard_exports()
    return field_map


def _wizard_missing_critical_fields() -> Sequence[str]:
    field_map, missing_fn, _logic_module, _update_fn = _wizard_exports()
    return tuple(missing_fn())


def _wizard_logic() -> ModuleType:
    field_map, _missing_fn, logic_module, _update_fn = _wizard_exports()
    return logic_module


def _wizard_update_profile(path: str, value: Any) -> None:
    field_map, _missing_fn, _logic_module, update_fn = _wizard_exports()
    update_fn(path, value)


STEP_LABELS: list[tuple[str, str]] = [
    ("onboarding", tr("Onboarding", "Onboarding")),
    ("company", tr("Unternehmen", "Company")),
    ("basic", tr("Basisdaten", "Basic info")),
    ("requirements", tr("Anforderungen", "Requirements")),
    ("compensation", tr("Leistungen & Benefits", "Rewards & Benefits")),
    ("process", tr("Prozess", "Process")),
    ("summary", tr("Summary", "Summary")),
]


@dataclass(slots=True)
class SidebarContext:
    """Convenience bundle with precomputed sidebar data."""

    profile: Mapping[str, Any]
    extraction_summary: Mapping[str, Any]
    skill_buckets: Mapping[str, Iterable[str]]
    missing_fields: set[str]
    missing_by_section: dict[int, list[str]]
    prefilled_sections: list[tuple[str, list[tuple[str, Any]]]]


@dataclass(slots=True)
class SidebarPlan:
    """Keep track of navigation placement for deferred sidebar rendering."""

    page: StreamlitPage | None
    branding: DeltaGenerator
    settings: DeltaGenerator
    navigation: DeltaGenerator
    body: DeltaGenerator


@dataclass(slots=True)
class _BrandingDisplay:
    company_name: str
    brand_color: str | None
    claim: str | None
    logo_src: str | None
    logo_is_uploaded: bool


def _store_branding_asset(upload: UploadedFile) -> None:
    """Persist an uploaded branding asset in session state."""

    try:
        data = upload.getvalue()
    except Exception:  # pragma: no cover - streamlit error surface
        return
    if not data:
        return
    st.session_state[StateKeys.COMPANY_BRANDING_ASSET] = {
        "name": getattr(upload, "name", ""),
        "type": getattr(upload, "type", ""),
        "data": bytes(data),
    }


def _clear_branding_asset() -> None:
    """Remove any cached branding upload."""

    st.session_state.pop(StateKeys.COMPANY_BRANDING_ASSET, None)
    for key in (
        UIKeys.COMPANY_BRANDING_UPLOAD,
        UIKeys.COMPANY_BRANDING_UPLOAD_LEGACY,
    ):
        st.session_state.pop(key, None)


def _persist_branding_upload_from_state(key: str) -> None:
    """Store or clear the branding asset based on the widget state."""

    value = st.session_state.get(key)
    if isinstance(value, UploadedFile):
        _store_branding_asset(value)
        return
    if value is None:
        _clear_branding_asset()


def _asset_to_data_uri(asset: Mapping[str, Any] | None) -> tuple[str | None, bool]:
    if not isinstance(asset, Mapping):
        return None, False
    data = asset.get("data")
    if not isinstance(data, (bytes, bytearray)):
        return None, False
    mime = str(asset.get("type") or "image/png").strip() or "image/png"
    if not mime.lower().startswith("image/"):
        return None, False
    encoded = b64encode(bytes(data)).decode("ascii")
    return f"data:{mime};base64,{encoded}", True


def _normalize_brand_color(value: str | None) -> str | None:
    if value is None:
        return None
    candidate = value.strip()
    if not candidate:
        return None
    upper = candidate.upper()
    if re.fullmatch(r"#?[0-9A-F]{6}", upper):
        return upper if upper.startswith("#") else f"#{upper}"
    return candidate


def _sanitize_logo_url(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"}:
        return None
    return value


def _coerce_brand_value(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    return ""


def _collect_branding_display() -> _BrandingDisplay | None:
    profile = st.session_state.get(StateKeys.PROFILE, {})
    company = profile.get("company") if isinstance(profile, Mapping) else {}
    if not isinstance(company, Mapping):
        company = {}

    cache = st.session_state.get(StateKeys.COMPANY_INFO_CACHE, {})
    branding = cache.get("branding") if isinstance(cache, Mapping) else {}
    if not isinstance(branding, Mapping):
        branding = {}

    def _pick(key: str) -> str:
        primary = _coerce_brand_value(company.get(key))
        if primary:
            return primary
        return _coerce_brand_value(branding.get(key))

    company_name = _pick("name") or _pick("brand_name")
    claim = _pick("claim")
    raw_color = _pick("brand_color")
    brand_color = _normalize_brand_color(raw_color)
    raw_logo_url = _sanitize_logo_url(_pick("logo_url"))

    uploaded_asset = st.session_state.get(StateKeys.COMPANY_BRANDING_ASSET)
    logo_src, is_uploaded = _asset_to_data_uri(uploaded_asset)
    if not logo_src:
        logo_src = raw_logo_url
        is_uploaded = False

    if not any((company_name, logo_src, brand_color, claim)):
        return None

    return _BrandingDisplay(
        company_name=company_name,
        brand_color=brand_color,
        claim=claim,
        logo_src=logo_src,
        logo_is_uploaded=is_uploaded,
    )


def _sync_brand_color() -> None:
    _wizard_update_profile(
        ProfilePaths.COMPANY_BRAND_COLOR.value, st.session_state.get(ProfilePaths.COMPANY_BRAND_COLOR.value)
    )


def _sync_brand_claim() -> None:
    _wizard_update_profile(ProfilePaths.COMPANY_CLAIM.value, st.session_state.get(ProfilePaths.COMPANY_CLAIM.value))


def _sync_logo_url() -> None:
    _wizard_update_profile(
        ProfilePaths.COMPANY_LOGO_URL.value, st.session_state.get(ProfilePaths.COMPANY_LOGO_URL.value)
    )


def _render_branding_overrides() -> None:
    st.caption(
        tr(
            "Passe Branding-Farben, Claim oder Logo manuell an.",
            "Manually adjust branding colour, claim, or logo.",
        )
    )
    logic = _wizard_logic()
    stored_color = logic.get_value(ProfilePaths.COMPANY_BRAND_COLOR.value)
    normalized_color = _normalize_brand_color(stored_color if isinstance(stored_color, str) else None)
    color_value = normalized_color or DEFAULT_BRAND_COLOR
    st.color_picker(
        tr("Markenfarbe überschreiben", "Override brand colour"),
        value=color_value,
        key=ProfilePaths.COMPANY_BRAND_COLOR.value,
        on_change=_sync_brand_color,
    )

    logic = _wizard_logic()
    current_claim = logic.get_value(ProfilePaths.COMPANY_CLAIM.value) or ""
    st.text_input(
        tr("Claim/Slogan anpassen", "Adjust claim/tagline"),
        value=str(current_claim),
        key=ProfilePaths.COMPANY_CLAIM.value,
        placeholder=tr("z. B. Einfach. Immer. Da.", "e.g., Simply. Always. There."),
        on_change=_sync_brand_claim,
    )

    logic = _wizard_logic()
    logo_key = ProfilePaths.COMPANY_LOGO_URL.value
    current_logo_value = logic.get_value(logo_key)
    current_logo = "" if current_logo_value is None else str(current_logo_value)

    session_logo_value = st.session_state.get(logo_key)
    if session_logo_value is None:
        st.session_state[logo_key] = current_logo
    elif not isinstance(session_logo_value, str):
        st.session_state[logo_key] = str(session_logo_value)

    st.text_input(
        tr("Logo-URL überschreiben", "Override logo URL"),
        value=current_logo,
        key=logo_key,
        placeholder="https://example.com/logo.svg",
        on_change=_sync_logo_url,
    )

    st.file_uploader(
        tr("Logo oder Branding-Datei hochladen", "Upload logo or brand asset"),
        type=["png", "jpg", "jpeg", "svg", "webp"],
        key=UIKeys.COMPANY_BRANDING_UPLOAD,
        on_change=partial(_persist_branding_upload_from_state, UIKeys.COMPANY_BRANDING_UPLOAD),
    )

    asset = st.session_state.get(StateKeys.COMPANY_BRANDING_ASSET)
    if isinstance(asset, Mapping):
        asset_name = asset.get("name") or tr("Hochgeladene Datei", "Uploaded file")
        st.caption(tr("Aktuelle Datei: {name}", "Current asset: {name}").format(name=asset_name))
        preview_src, _uploaded = _asset_to_data_uri(asset)
        if preview_src:
            try:
                st.image(preview_src, width=160)
            except Exception:  # pragma: no cover - preview guard
                pass
        if st.button(tr("Datei entfernen", "Remove file"), key="company.branding.remove.sidebar"):
            _clear_branding_asset()
            st.rerun()


def render_sidebar(
    logo_asset: LogoRenderable | None = None,
    *,
    logo_bytes: bytes | None = None,
    logo_data_uri: str | None = None,
    pages: Sequence[st.Page] | None = None,
    plan: SidebarPlan | None = None,
    defer: bool = False,
) -> SidebarPlan | StreamlitPage | None:
    """Render the dynamic wizard sidebar with contextual content."""

    _ensure_ui_defaults()

    if logo_asset is None and logo_bytes:
        buffer = BytesIO(logo_bytes)
        setattr(buffer, "name", "app_logo.gif")
        logo_asset = buffer
        if logo_data_uri is None:
            logo_data_uri = f"data:image/png;base64,{b64encode(logo_bytes).decode('ascii')}"

    if plan is None:
        plan = _prepare_sidebar_plan(pages)
        if defer:
            return plan

    return _render_sidebar_sections(plan, logo_asset, logo_data_uri)


def _prepare_sidebar_plan(
    pages: Sequence[st.Page] | None,
) -> SidebarPlan:
    """Create sidebar containers and navigation without rendering contextual data."""

    with st.sidebar:
        branding = st.container()
        settings = st.container()
        navigation = st.container()
        body = st.container()

    current_page: StreamlitPage | None = None
    if pages is not None:
        with navigation:
            current_page = st.navigation(pages)

    return SidebarPlan(
        page=current_page,
        branding=branding,
        settings=settings,
        navigation=navigation,
        body=body,
    )


def _render_sidebar_sections(
    plan: SidebarPlan,
    logo_asset: LogoRenderable | None,
    logo_data_uri: str | None,
) -> StreamlitPage | None:
    """Render branding, settings, and contextual sections in the sidebar."""

    context = _build_context()

    with plan.branding:
        if logo_asset or logo_data_uri:
            _render_branding(logo_asset, logo_data_uri)

    with plan.settings:
        _render_settings()

    with plan.body:
        current_step = st.session_state.get(StateKeys.STEP, 0)
        if current_step > 0:
            _render_hero(context)
            st.divider()
            _render_step_context(context)
        st.divider()
        _render_salary_expectation(context.profile)

    return plan.page


def _render_branding(
    logo_asset: LogoRenderable | None,
    logo_data_uri: str | None,
) -> None:
    """Display company-specific branding when available, otherwise fallback."""

    if not _render_company_branding():
        _render_app_branding(logo_asset, logo_data_uri)
    else:
        _render_app_version()


def _render_app_branding(
    logo_asset: LogoRenderable | None,
    logo_data_uri: str | None,
) -> None:
    if logo_asset is not None:
        st.image(logo_asset, use_container_width=True)
    elif logo_data_uri:
        alt_text = html.escape(
            tr(
                "Cognitive Needs Logo",
                "Cognitive Needs logo",
            )
        )
        st.markdown(
            """
            <img
                src="%s"
                alt="%s"
                class="sidebar-hero__logo"
                style="max-width: 100%%; height: auto; display: block;"
            />
            """
            % (html.escape(logo_data_uri), alt_text),
            unsafe_allow_html=True,
        )
    st.markdown('<div style="margin-bottom: 0.5rem;"></div>', unsafe_allow_html=True)
    _render_app_version()


def _render_app_version() -> None:
    app_version = st.session_state.get("app_version")
    if app_version:
        st.caption(tr(f"Version {app_version}", f"Version {app_version}"))


def _render_company_branding() -> bool:
    """Inject cached company branding assets into the sidebar hero."""

    display = _collect_branding_display()
    if display is None:
        return False

    eyebrow = tr("Unternehmen", "Company")
    company_name = display.company_name or ""
    title = html.escape(company_name or eyebrow)
    claim_html = f'<p class="sidebar-hero__subtitle">{html.escape(display.claim)}</p>' if display.claim else ""

    visual_html: str
    if display.logo_src:
        safe_src = html.escape(display.logo_src)
        alt = html.escape(company_name or eyebrow)
        visual_html = f'<img src="{safe_src}" alt="{alt} logo" class="sidebar-hero__logo" />'
    else:
        initial = (company_name[:1] if company_name else "•").upper()
        visual_html = f'<div class="sidebar-hero__avatar">{html.escape(initial)}</div>'

    gradient_color: str | None = None
    text_color: str | None = None
    if display.brand_color:
        accessible = _accessible_brand_colors(display.brand_color)
        if accessible:
            gradient_color, text_color = accessible

    if gradient_color and text_color:
        st.markdown(
            """
            <style>
            .sidebar-hero.sidebar-hero--company {
                background: linear-gradient(135deg, %s1A, %s);
                border-color: %s33;
            }
            .sidebar-hero.sidebar-hero--company .sidebar-hero__title,
            .sidebar-hero.sidebar-hero--company .sidebar-hero__subtitle,
            .sidebar-hero.sidebar-hero--company .sidebar-hero__eyebrow {
                color: %s !important;
            }
            .sidebar-hero__avatar {
                background: %s;
                color: %s;
            }
            </style>
            """
            % (
                gradient_color,
                gradient_color,
                gradient_color,
                text_color,
                gradient_color,
                text_color,
            ),
            unsafe_allow_html=True,
        )

    st.markdown(
        """
        <div class="sidebar-hero sidebar-hero--company">
            <div class="sidebar-hero__visual">%s</div>
            <div>
                <p class="sidebar-hero__eyebrow">%s</p>
                <h4 class="sidebar-hero__title">%s</h4>
                %s
            </div>
        </div>
        """
        % (visual_html, html.escape(eyebrow), title, claim_html),
        unsafe_allow_html=True,
    )
    return True


def _brand_text_color(hex_color: str) -> str:
    value = hex_color.lstrip("#")
    if len(value) != 6:
        return "#FFFFFF"
    try:
        r = int(value[0:2], 16)
        g = int(value[2:4], 16)
        b = int(value[4:6], 16)
    except ValueError:
        return "#FFFFFF"
    luminance = 0.299 * r + 0.587 * g + 0.114 * b
    return "#000000" if luminance >= 186 else "#FFFFFF"


AA_CONTRAST_THRESHOLD = 4.5


def _accessible_brand_colors(hex_color: str) -> tuple[str, str] | None:
    """Return brand/background and text colours when the contrast meets AA."""

    normalized = hex_color.upper()
    if not normalized.startswith("#"):
        normalized = f"#{normalized}"

    brand_rgb = _hex_to_rgb(normalized)
    text_hex = _brand_text_color(normalized)
    text_rgb = _hex_to_rgb(text_hex)
    if brand_rgb is None or text_rgb is None:
        return None

    contrast = _contrast_ratio(brand_rgb, text_rgb)
    if contrast < AA_CONTRAST_THRESHOLD:
        return None

    return normalized, text_hex


def _hex_to_rgb(value: str) -> tuple[int, int, int] | None:
    stripped = value.lstrip("#")
    if len(stripped) != 6:
        return None
    try:
        return tuple(int(stripped[i : i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return None


def _relative_luminance(rgb: tuple[int, int, int]) -> float:
    def _channel(component: int) -> float:
        srgb = component / 255
        if srgb <= 0.03928:
            return srgb / 12.92
        return ((srgb + 0.055) / 1.055) ** 2.4

    r, g, b = rgb
    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def _contrast_ratio(color_a: tuple[int, int, int], color_b: tuple[int, int, int]) -> float:
    lighter = max(_relative_luminance(color_a), _relative_luminance(color_b))
    darker = min(_relative_luminance(color_a), _relative_luminance(color_b))
    return (lighter + 0.05) / (darker + 0.05)


def _ensure_ui_defaults() -> None:
    """Initialise language and theme toggles in session state."""

    if UIKeys.LANG_SELECT not in st.session_state:
        st.session_state[UIKeys.LANG_SELECT] = st.session_state.get("lang", "de")
    st.session_state["lang"] = st.session_state[UIKeys.LANG_SELECT]
    if "ui.lang_toggle" not in st.session_state:
        st.session_state["ui.lang_toggle"] = st.session_state[UIKeys.LANG_SELECT] == "en"
    if "ui.dark_mode" not in st.session_state:
        st.session_state["ui.dark_mode"] = st.session_state.get("dark_mode", True)
    _ensure_style_defaults()


def _ensure_style_defaults() -> None:
    """Ensure a valid style variant is present in session state."""

    lang_code = st.session_state.get("lang", "de")
    default_key = STYLE_VARIANT_ORDER[1]
    current_key = st.session_state.get(UIKeys.TONE_SELECT)
    if current_key not in STYLE_VARIANTS:
        st.session_state[UIKeys.TONE_SELECT] = default_key
    _sync_style_instruction(lang_code)


def _sync_style_instruction(lang_code: str) -> None:
    """Update derived tone instructions for the selected style variant."""

    selected_key = st.session_state.get(UIKeys.TONE_SELECT, STYLE_VARIANT_ORDER[1])
    variant = STYLE_VARIANTS.get(selected_key)
    if variant is None:
        fallback = str(selected_key or "").strip()
        st.session_state["tone"] = fallback
        st.session_state["style_prompt_hint"] = fallback
        return

    st.session_state["tone"] = tr(*variant.instruction, lang=lang_code)
    st.session_state["style_prompt_hint"] = tr(*variant.prompt_hint, lang=lang_code)


def _build_context() -> SidebarContext:
    """Collect data used across sidebar sections."""

    profile: Mapping[str, Any] = st.session_state.get(StateKeys.PROFILE, {})
    summary: Mapping[str, Any] = st.session_state.get(StateKeys.EXTRACTION_SUMMARY, {})
    skill_buckets: Mapping[str, Iterable[str]] = st.session_state.get(StateKeys.SKILL_BUCKETS, {})

    missing = set(_wizard_missing_critical_fields())
    missing_by_section: dict[int, list[str]] = {}
    for field in missing:
        section = _wizard_field_section_map().get(field)
        if section is None:
            continue
        missing_by_section.setdefault(section, []).append(field)

    prefilled_sections = build_prefilled_sections()

    return SidebarContext(
        profile=profile,
        extraction_summary=summary,
        skill_buckets=skill_buckets,
        missing_fields=missing,
        missing_by_section=missing_by_section,
        prefilled_sections=prefilled_sections,
    )


def _render_settings() -> None:
    """Show language and theme controls."""

    def _on_theme_toggle() -> None:
        st.session_state["dark_mode"] = st.session_state["ui.dark_mode"]

    def _on_lang_toggle() -> None:
        st.session_state[UIKeys.LANG_SELECT] = "en" if st.session_state["ui.lang_toggle"] else "de"
        st.session_state["lang"] = st.session_state[UIKeys.LANG_SELECT]
        _sync_style_instruction(st.session_state["lang"])

    st.markdown(f"### ⚙️ {tr('Einstellungen', 'Settings')}")
    dark_col, lang_col = st.columns(2)
    with dark_col:
        is_dark = st.session_state.get("ui.dark_mode", True)
        dark_label = (
            tr("🌙 Dunkelmodus aktiv", "🌙 Dark mode active")
            if is_dark
            else tr("☀️ Hellmodus aktiv", "☀️ Light mode active")
        )
        st.toggle(
            dark_label,
            key="ui.dark_mode",
            on_change=_on_theme_toggle,
        )
    with lang_col:
        lang_is_en = st.session_state.get("ui.lang_toggle", False)
        lang_label = "🇬🇧 English" if lang_is_en else "🇩🇪 Deutsch"
        st.toggle(
            lang_label,
            key="ui.lang_toggle",
            on_change=_on_lang_toggle,
        )

    st.markdown(f"#### 🎨 {tr('Stil & Tonalität', 'Style & tone')}")
    lang_code = st.session_state.get("lang", "de")
    options = list(STYLE_VARIANT_ORDER)

    def _format_style(option: str) -> str:
        variant = STYLE_VARIANTS.get(option)
        if variant is None:
            return option.replace("_", " ").title()
        return tr(*variant.label, lang=lang_code)

    selected_style = st.radio(
        tr("Ton auswählen", "Choose tone"),
        options,
        key=UIKeys.TONE_SELECT,
        format_func=_format_style,
    )
    variant = STYLE_VARIANTS.get(selected_style)
    if variant is not None:
        st.caption(tr(*variant.description, lang=lang_code))
        st.caption(tr(*variant.example, lang=lang_code))

    _sync_style_instruction(lang_code)

    st.markdown(f"#### 🪪 {tr('Branding', 'Branding')}")
    with st.expander(tr("Branding-Einstellungen", "Branding settings"), expanded=False):
        _render_branding_overrides()


def _render_hero(context: SidebarContext) -> None:
    """Render extracted data grouped by wizard step."""

    st.markdown(f"### 🗂️ {tr('Schnellüberblick', 'Quick snapshot')}")

    step_order, step_entries = _build_initial_extraction_entries(context)
    if not any(step_entries.values()):
        st.caption(
            tr(
                "Sobald du Daten importierst, erscheinen hier die wichtigsten Ergebnisse.",
                "As soon as you import data the top findings will appear here.",
            )
        )
        return

    step_labels = {key: label for key, label in STEP_LABELS}
    for idx, step_key in enumerate(step_order):
        entries = step_entries.get(step_key, [])
        if not entries:
            continue
        label = step_labels.get(step_key, step_key.title())
        with st.expander(label, expanded=idx == 0):
            for field_label, value in entries:
                safe_label = html.escape(field_label)
                safe_value = html.escape(value)
                st.markdown(
                    f"- **{safe_label}**: {safe_value}",
                    unsafe_allow_html=True,
                )


def _render_step_context(context: SidebarContext) -> None:
    """Render contextual guidance for the active wizard step."""

    current = st.session_state.get(StateKeys.STEP, 0)

    renderers = {
        0: _render_onboarding_context,
        1: _render_company_context,
        2: _render_basic_context,
        3: _render_requirements_context,
        4: _render_compensation_context,
        5: _render_process_context,
        6: _render_summary_context,
    }
    renderer = renderers.get(current)
    if renderer is None:
        st.markdown(f"### 🧭 {tr('Kontext zum Schritt', 'Step context')}")
        st.caption(tr("Keine Kontextinformationen verfügbar.", "No context available."))
        return

    if current != 0:
        st.markdown(f"### 🧭 {tr('Kontext zum Schritt', 'Step context')}")

    renderer(context)


def _build_initial_extraction_entries(
    context: SidebarContext,
) -> tuple[list[str], dict[str, list[tuple[str, str]]]]:
    """Return ordered step keys with their extracted entries."""

    step_order = [key for key, _ in STEP_LABELS]
    if not step_order:
        return [], {}

    step_entries: dict[str, list[tuple[str, str]]] = {key: [] for key in step_order}

    summary = context.extraction_summary
    known_step_keys = set(step_order)
    if isinstance(summary, Mapping):
        is_step_grouped = summary and all(
            isinstance(value, Mapping) and key in known_step_keys for key, value in summary.items()
        )
        if is_step_grouped:
            for step_key, values in summary.items():
                entries = step_entries.setdefault(step_key, [])
                for label, value in values.items():
                    preview = preview_value_to_text(value)
                    if preview:
                        entries.append((str(label), preview))
        else:
            entries = step_entries.setdefault("onboarding", [])
            for label, value in summary.items():
                preview = preview_value_to_text(value)
                if preview:
                    entries.append((str(label), preview))

    section_map = _initial_extraction_section_map()
    for section_label, items in context.prefilled_sections:
        step_key = section_map.get(section_label)
        if not step_key:
            continue
        entries = step_entries.setdefault(step_key, [])
        for path, value in items:
            preview = preview_value_to_text(value)
            if not preview:
                continue
            entries.append((_format_field_name(path), preview))

    return step_order, step_entries


def _initial_extraction_section_map() -> dict[str, str]:
    """Return mapping of section labels to wizard step keys."""

    return {
        tr("Unternehmen", "Company"): "company",
        tr("Basisdaten", "Basic info"): "basic",
        tr("Beschäftigung", "Employment"): "basic",
        tr("Anforderungen", "Requirements"): "requirements",
        tr("Leistungen & Benefits", "Rewards & Benefits"): "compensation",
        tr("Prozess", "Process"): "process",
    }


def _render_onboarding_context(_: SidebarContext) -> None:
    missing = st.session_state.get(StateKeys.EXTRACTION_MISSING, [])
    if missing:
        st.warning(
            tr(
                "Folgende Pflichtfelder fehlen noch: ",
                "The following critical fields are still missing: ",
            )
            + ", ".join(_format_field_name(item) for item in missing[:6])
        )


def _render_company_context(context: SidebarContext) -> None:
    st.markdown(f"#### {tr('Unternehmensdaten', 'Company details')}")
    company = context.profile.get("company", {})
    if not isinstance(company, Mapping):
        company = {}
    display_fields: list[tuple[str, str]] = [
        ("name", tr("Unternehmen", "Company")),
        ("industry", tr("Branche", "Industry")),
        ("hq_location", tr("Hauptsitz", "Headquarters")),
        ("size", tr("Größe", "Size")),
        ("website", tr("Website", "Website")),
        ("contact_name", tr("Kontaktperson", "Primary contact")),
        ("contact_email", tr("Kontakt-E-Mail", "Contact email")),
        ("contact_phone", tr("Telefon", "Phone")),
        ("mission", tr("Mission", "Mission")),
    ]

    rendered = 0
    for key, label in display_fields:
        raw_value = company.get(key)
        if raw_value is None:
            continue
        value = str(raw_value).strip()
        if not value:
            continue
        rendered += 1
        safe_label = html.escape(label)
        safe_value = html.escape(value)
        st.markdown(
            f"- **{safe_label}**: {safe_value}",
            unsafe_allow_html=True,
        )

    if rendered == 0:
        st.caption(tr("Noch keine Firmendaten hinterlegt.", "No company details yet."))
        return

    _render_missing_hint(context, section=1)


def _render_basic_context(context: SidebarContext) -> None:
    st.markdown(f"#### {tr('Rollenüberblick', 'Role snapshot')}")
    position = context.profile.get("position", {})
    location = context.profile.get("location", {})
    if not position and not location:
        st.caption(tr("Noch keine Basisdaten hinterlegt.", "No basic info yet."))
    else:
        for key in ("job_title", "seniority_level", "department"):
            value = position.get(key)
            if value:
                st.markdown(f"- **{_format_field_name(f'position.{key}')}**: {value}")
        city = location.get("primary_city")
        country = location.get("country")
        if city or country:
            st.markdown(f"- **{tr('Standort', 'Location')}:** {', '.join(part for part in [city, country] if part)}")
    employment = context.profile.get("employment", {})
    if employment.get("work_policy"):
        policy = employment["work_policy"]
        st.caption(tr("Aktuelle Arbeitsform:", "Current work policy:") + f" {policy}")
    _render_missing_hint(context, section=2)


def _render_requirements_context(context: SidebarContext) -> None:
    st.markdown(f"#### {tr('Skill-Portfolio', 'Skill portfolio')}")
    must = list(context.skill_buckets.get("must", []))
    nice = list(context.skill_buckets.get("nice", []))
    if not must and not nice:
        st.caption(
            tr(
                "Lege Must-have und Nice-to-have Skills fest, um das Profil zu schärfen.",
                "Add must-have and nice-to-have skills to sharpen the profile.",
            )
        )
    if must:
        st.markdown(f"**{tr('Must-haves', 'Must-haves')}**: {', '.join(must[:12])}")
    if nice:
        st.markdown(f"**{tr('Nice-to-haves', 'Nice-to-haves')}**: {', '.join(nice[:12])}")
    missing_esco = [
        str(skill).strip()
        for skill in st.session_state.get(StateKeys.ESCO_MISSING_SKILLS, []) or []
        if isinstance(skill, str) and str(skill).strip()
    ]
    if missing_esco:
        outstanding = ", ".join(dict.fromkeys(missing_esco))
        st.warning(
            tr(
                "ESCO meldet noch fehlende Essentials: {skills}",
                "ESCO still flags missing essentials: {skills}",
            ).format(skills=outstanding)
        )
    _render_missing_hint(context, section=3)


def _render_compensation_context(context: SidebarContext) -> None:
    st.markdown(f"#### {tr('Vergütung & Benefits', 'Compensation & benefits')}")
    compensation = context.profile.get("compensation", {})
    salary_min = compensation.get("salary_min")
    salary_max = compensation.get("salary_max")
    currency = compensation.get("currency") or ""
    if salary_min or salary_max:
        st.markdown(
            f"- **{tr('Aktuelle Spanne', 'Current range')}**: {format_salary_range(salary_min, salary_max, currency)}"
        )
    if compensation.get("variable_pay"):
        st.markdown(f"- **{tr('Variable Vergütung', 'Variable pay')}**: ✅")
    benefits = compensation.get("benefits", [])
    if benefits:
        st.markdown(f"- **{tr('Benefits', 'Benefits')}**: {', '.join(benefits[:8])}")
    if not (salary_min or salary_max or benefits):
        st.caption(
            tr(
                "Trage Gehaltsdaten und Benefits ein, um Erwartungen abgleichen zu können.",
                "Add salary details and benefits to compare expectations.",
            )
        )


def _render_process_context(context: SidebarContext) -> None:
    st.markdown(f"#### {tr('Hiring-Prozess', 'Hiring process')}")
    process = context.profile.get("process", {})
    stakeholders = process.get("stakeholders", [])
    phases = process.get("phases", [])
    if stakeholders:
        lead = next((s for s in stakeholders if s.get("primary")), None)
        if lead:
            st.markdown(f"- **{tr('Lead Recruiter', 'Lead recruiter')}**: {lead.get('name', '')}")
        st.markdown(f"- **{tr('Stakeholder gesamt', 'Stakeholders total')}**: {len(stakeholders)}")
    if phases:
        st.markdown(f"- **{tr('Prozessphasen', 'Process phases')}**: {len(phases)}")
    if process.get("notes"):
        st.caption(f"{tr('Hinweis', 'Note')}: {process['notes']}")
    if not (stakeholders or phases or process.get("notes")):
        st.caption(
            tr(
                "Lege Verantwortliche und Phasen fest, um einen transparenten Ablauf zu sichern.",
                "Define stakeholders and phases to keep the process transparent.",
            )
        )


def _render_summary_context(context: SidebarContext) -> None:
    st.markdown(f"#### {tr('Bereit für den Export', 'Export readiness')}")
    downloads = [
        (UIKeys.JOB_AD_OUTPUT, tr("Job-Ad erstellt", "Job ad generated")),
        (UIKeys.INTERVIEW_OUTPUT, tr("Interview-Guide erstellt", "Interview guide generated")),
    ]
    for key, label in downloads:
        available = bool(st.session_state.get(key))
        icon = "✅" if available else "⏳"
        st.markdown(f"- {icon} {label}")

    usage = st.session_state.get(StateKeys.USAGE)
    if usage:
        in_tok, out_tok, total_tok = usage_totals(usage)
        summary = tr("Tokenverbrauch", "Token usage") + f": {in_tok} + {out_tok} = {total_tok}"
        table = build_usage_markdown(usage)
        if table:
            with st.expander(summary):
                st.markdown(table)
        else:
            st.caption(summary)


def _render_missing_hint(context: SidebarContext, *, section: int) -> None:
    missing = context.missing_by_section.get(section, [])
    if not missing:
        return
    fields = ", ".join(_format_field_name(field) for field in missing[:6])
    st.warning(tr("Fehlende Pflichtfelder:", "Missing mandatory fields:") + f" {fields}")


def _render_salary_expectation(profile: Mapping[str, Any]) -> None:
    st.markdown(f"### 💰 {tr('Gehaltserwartung', 'Salary expectation')}")
    llm_available = is_llm_available()
    if st.button(
        tr("Gehaltserwartung aktualisieren", "Update salary expectation"),
        width="stretch",
        key="update_salary_expectation",
        disabled=not llm_available,
    ):
        with st.spinner(tr("Berechne neue Gehaltseinschätzung…", "Calculating salary estimate…")):
            estimate_salary_expectation()

    if not llm_available:
        st.caption(llm_disabled_message())

    estimate: Mapping[str, Any] | None = st.session_state.get(UIKeys.SALARY_ESTIMATE)
    explanation = st.session_state.get(UIKeys.SALARY_EXPLANATION)
    timestamp: str | None = st.session_state.get(UIKeys.SALARY_REFRESH)

    if timestamp:
        try:
            dt = datetime.fromisoformat(timestamp)
            st.caption(tr("Zuletzt aktualisiert", "Last refreshed") + f": {dt.strftime('%d.%m.%Y %H:%M')}")
        except ValueError:
            pass

    if not estimate:
        st.caption(
            tr(
                "Noch keine Schätzung vorhanden. Ergänze Jobtitel und Standort, um zu starten.",
                "No estimate yet. Provide job title and location to get started.",
            )
        )
        _render_explanation_text(explanation)
        return

    currency = estimate.get("currency") or profile.get("compensation", {}).get("currency")
    salary_min = estimate.get("salary_min")
    salary_max = estimate.get("salary_max")
    st.markdown(
        f"**{tr('Erwartete Spanne', 'Expected range')}**: {format_salary_range(salary_min, salary_max, currency)}"
    )

    user_comp = profile.get("compensation", {})
    user_min = user_comp.get("salary_min")
    user_max = user_comp.get("salary_max")
    user_currency = user_comp.get("currency") or currency

    if user_min or user_max:
        st.markdown(
            f"**{tr('Eingegebene Spanne', 'Entered range')}**: {format_salary_range(user_min, user_max, user_currency)}"
        )

    source_label = _salary_source_label(str(estimate.get("source", "")))
    if source_label:
        st.caption(tr("Quelle der Schätzung: {source}", "Estimate source: {source}").format(source=source_label))

    factors = prepare_salary_factor_entries(
        explanation,
        benchmark_currency=currency,
        user_currency=user_currency,
    )
    if factors:
        _render_salary_factor_section(factors)
    else:
        _render_explanation_text(explanation)


def _render_salary_factor_section(factors: list[SalaryFactorEntry]) -> None:
    st.markdown(f"### {tr('Größte Einflussfaktoren', 'Top influencing factors')}")

    max_count = len(factors)
    default_count = min(3, max_count)
    factor_count = st.slider(
        tr(
            "Anzahl der angezeigten Einflussfaktoren",
            "Number of influencing factors to show",
        ),
        min_value=1,
        max_value=max_count,
        value=default_count,
        key="ui.salary.factor.count",
    )

    top_factors = sorted(
        factors,
        key=lambda item: item.magnitude,
        reverse=True,
    )[:factor_count]

    if not top_factors:
        return

    fig = build_factor_influence_chart(top_factors)
    st.plotly_chart(fig, use_container_width=True)
    _render_factor_details(top_factors)


def _render_factor_details(factors: Sequence[SalaryFactorEntry]) -> None:
    for factor in factors:
        st.markdown(f"**{factor.label}**: {factor.value_display}")
        if factor.impact_summary:
            st.caption(factor.impact_summary)
        if factor.explanation:
            st.caption(factor.explanation)


def _render_explanation_text(explanation: object) -> None:
    if isinstance(explanation, str) and explanation:
        st.caption(explanation)
    elif explanation and not isinstance(explanation, str):
        st.caption(str(explanation))


def _salary_source_label(source: str) -> str:
    lookup = {
        "model": tr("KI-Modell", "AI model"),
        "fallback": tr("Benchmark-Fallback", "Benchmark fallback"),
    }
    label = lookup.get(source)
    if label:
        return label
    return source.strip()


def _chip_button_with_tooltip(
    label: str,
    *,
    key: str,
    type: str,
    use_container_width: bool,
    help: str | None = None,
) -> bool:
    tooltip = help or label
    return st.button(
        label,
        key=key,
        type=type,
        use_container_width=use_container_width,
        help=tooltip,
    )


def _format_field_name(path: str) -> str:
    """Return a human readable field name."""

    return path.replace("_", " ").replace(".", " → ").title()


__all__ = ["SidebarPlan", "render_sidebar"]
