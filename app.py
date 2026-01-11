# app.py — Cognitive Needs (clean entrypoint, single source of truth)
from __future__ import annotations

from base64 import b64encode
from hashlib import sha256
from io import BytesIO
import json
import mimetypes
from pathlib import Path
import sys
from typing import Callable, Mapping, Sequence, cast

from PIL import Image, ImageEnhance, UnidentifiedImageError
import streamlit as st

APP_ROOT = Path(__file__).resolve().parent
for candidate in (APP_ROOT, APP_ROOT.parent):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

# Sidebar + favicon visuals use the former onboarding animation asset
APP_LOGO_PATH = APP_ROOT / "images" / "animation_pulse_Default_7kigl22lw.gif"
try:
    APP_LOGO_BYTES: bytes | None = APP_LOGO_PATH.read_bytes()
except FileNotFoundError:
    APP_LOGO_BYTES = None

APP_LOGO_BUFFER: BytesIO | None = None
APP_LOGO_IMAGE: Image.Image | None = None
APP_LOGO_DATA_URI: str | None = None

if APP_LOGO_BYTES:
    APP_LOGO_BUFFER = BytesIO(APP_LOGO_BYTES)
    setattr(APP_LOGO_BUFFER, "name", APP_LOGO_PATH.name)

    try:
        with Image.open(BytesIO(APP_LOGO_BYTES)) as loaded_logo:
            copied_logo = loaded_logo.copy()
        copied_logo.load()
        APP_LOGO_IMAGE = copied_logo
    except UnidentifiedImageError:
        APP_LOGO_IMAGE = None

    mime_type, _encoding = mimetypes.guess_type(APP_LOGO_PATH.name)
    safe_mime = mime_type or "image/png"
    APP_LOGO_DATA_URI = f"data:{safe_mime};base64,{b64encode(APP_LOGO_BYTES).decode('ascii')}"

from openai import OpenAI  # noqa: E402

from config import (  # noqa: E402
    LLM_ENABLED,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    OPENAI_ORGANIZATION,
    OPENAI_PROJECT,
)
from llm.model_router import pick_model_for_tier  # noqa: E402
from utils.telemetry import setup_tracing  # noqa: E402
from utils.i18n import tr  # noqa: E402
from constants.keys import StateKeys  # noqa: E402
from state import ensure_state  # noqa: E402
from state.autosave import maybe_render_autosave_prompt  # noqa: E402
from components.chatkit_widget import inject_chatkit_script  # noqa: E402
from components import stepper as legacy_stepper  # noqa: E402
from ui.wizard_uxkit_guidedflow_20260110 import (  # noqa: E402
    Wizard,
    WizardStep,
    inject_wizard_uxkit_css,
    render_context_bar,
    render_progress_and_microcopy,
    render_saved_badge_if_recent,
    render_stepper,
)
from wizard.step_registry import (  # noqa: E402
    WIZARD_STEPS,
    resolve_active_step_keys,
    resolve_nearest_active_step_key,
)
from wizard._logic import get_in  # noqa: E402
import sidebar  # noqa: E402
from wizard import run_wizard  # noqa: E402

APP_VERSION = "1.2.0"
WIZARD_ID = "guidedflow"
USE_FORM_PANEL_FADE = False
setup_tracing()

# --- Page config early (keine doppelten Titel/Icon-Resets) ---
st.set_page_config(
    page_title="Cognitive Staffing — Recruitment Need Analysis",
    page_icon=APP_LOGO_IMAGE or APP_LOGO_BUFFER or "🧭",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Helpers zum Laden lokaler JSON-Configs ---
ROOT = APP_ROOT
ensure_state()
st.session_state.setdefault(StateKeys.APP_VERSION, APP_VERSION)
st.session_state[StateKeys.WIZARD_STEP_FORM_MODE] = USE_FORM_PANEL_FADE
st.session_state[StateKeys.WIZARD_STEP_FORM_FADE] = USE_FORM_PANEL_FADE

MODEL_MAP = cast(dict[str, str] | None, st.session_state.get("model_map"))
MODEL_TIERS = ("FAST", "QUALITY", "LONG_CONTEXT")
if LLM_ENABLED:
    if MODEL_MAP is None:
        MODEL_MAP = {}
        st.session_state["model_map"] = MODEL_MAP
    if not MODEL_MAP or any(tier not in MODEL_MAP for tier in MODEL_TIERS):
        try:
            router_client = OpenAI(
                api_key=OPENAI_API_KEY or None,
                base_url=OPENAI_BASE_URL or None,
                organization=OPENAI_ORGANIZATION or None,
                project=OPENAI_PROJECT or None,
            )
            for tier in MODEL_TIERS:
                if tier in MODEL_MAP:
                    continue
                MODEL_MAP[tier] = pick_model_for_tier(router_client, tier)
            st.session_state["model_map"] = MODEL_MAP
            st.session_state[StateKeys.ROUTER_MODEL_LOGGED] = True
            print(f"[MODEL_ROUTER_V3] using model_map={MODEL_MAP}")
        except Exception as exc:  # pragma: no cover - defensive startup logging
            print(f"[MODEL_ROUTER_V3] unable to resolve model map: {exc}")
    elif not st.session_state.get(StateKeys.ROUTER_MODEL_LOGGED):
        print(f"[MODEL_ROUTER_V3] using model_map={MODEL_MAP}")
        st.session_state[StateKeys.ROUTER_MODEL_LOGGED] = True
else:
    print("[MODEL_ROUTER_V3] OpenAI API key not configured; model routing skipped.")

if st.session_state.get("openai_api_key_missing"):
    st.warning(
        tr(
            "⚠️ OpenAI-API-Schlüssel nicht gesetzt. Bitte in der Umgebung konfigurieren, um KI-Funktionen zu nutzen.",
            "⚠️ OpenAI API key not set. Please configure it in the environment to use AI features.",
        )
    )
if st.session_state.get("openai_base_url_invalid"):
    st.warning(
        tr(
            "⚠️ OPENAI_BASE_URL scheint ungültig zu sein und wird ignoriert.",
            "⚠️ OPENAI_BASE_URL appears invalid and will be ignored.",
        )
    )
if st.session_state.get("openai_unavailable"):
    st.error(
        tr(
            "🚫 OpenAI-Kontingent aufgebraucht. KI-Funktionen sind vorübergehend deaktiviert.",
            "🚫 OpenAI quota exceeded. AI features are temporarily disabled.",
        )
    )

maybe_render_autosave_prompt()


@st.cache_data(show_spinner=False)
def _load_background_image(dark_mode: bool) -> str | None:
    """Return the base64 encoded background image, adjusting for the theme."""

    bg_path = ROOT / "images" / "AdobeStock_506577005.jpeg"
    try:
        with Image.open(bg_path) as image:
            processed_image = image.convert("RGB")
            if not dark_mode:
                brightness = ImageEnhance.Brightness(processed_image)
                processed_image = brightness.enhance(0.55)

            buffer = BytesIO()
            processed_image.save(buffer, format="JPEG", quality=90)
    except FileNotFoundError:
        return None

    return b64encode(buffer.getvalue()).decode()


def inject_global_css() -> None:
    """Inject the global stylesheet and background image."""

    dark_mode = st.session_state.get("dark_mode", True)
    theme = "cognitive_needs.css" if dark_mode else "cognitive_needs_light.css"
    css = (ROOT / "styles" / theme).read_text(encoding="utf-8")
    encoded_bg = _load_background_image(dark_mode)
    bg_style = f":root {{ --bg-image: url('data:image/jpeg;base64,{encoded_bg}'); }}" if encoded_bg else ""
    st.markdown(
        f"<style>{css}\n{bg_style}</style>",
        unsafe_allow_html=True,
    )


def inject_layout_stability_css() -> None:
    """Ensure reserved UI space for stable text areas in the wizard."""

    st.markdown(
        """
        <style>
        div[data-testid="stTextArea"] textarea {
            min-height: 7.5rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _profile_checksum(profile: Mapping[str, object] | None) -> str:
    payload = json.dumps(profile or {}, sort_keys=True, default=str)
    return sha256(payload.encode("utf-8")).hexdigest()


def _has_value(profile: Mapping[str, object], path: str) -> bool:
    value = get_in(profile, path)
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return value is not None


def _required_validator(step_key: str, msg: str) -> Callable[[Wizard], tuple[bool, str]]:
    def _validate(wiz: Wizard) -> tuple[bool, str]:
        key = wiz.k("required", step_key)
        val = st.session_state.get(key)
        ok = bool(val and str(val).strip())
        return ok, ("" if ok else msg)

    return _validate


def _build_display_wizard(
    active_keys: Sequence[str],
    lang: str,
    profile: Mapping[str, object],
) -> Wizard:
    steps: list[WizardStep] = []
    step_map = {step.key: step for step in WIZARD_STEPS}
    required_map: dict[str, Sequence[str]] = {}
    for key in active_keys:
        step = step_map.get(key)
        if step is None:
            continue
        required_fields = step.required_fields
        validate = None
        if required_fields:
            required_map[step.key] = required_fields
            validate = _required_validator(
                step.key,
                tr(
                    "Bitte fülle die Pflichtfelder aus, bevor du fortfährst.",
                    "Please complete the required fields before continuing.",
                    lang=lang,
                ),
            )
        steps.append(
            WizardStep(
                id=step.key,
                label=tr(*step.label, lang=lang),
                title=tr(*step.panel_header, lang=lang),
                render=lambda _wiz: None,
                validate=validate,
            )
        )
    if not steps:
        steps = [
            WizardStep(
                id=step.key,
                label=tr(*step.label, lang=lang),
                title=tr(*step.panel_header, lang=lang),
                render=lambda _wiz: None,
                validate=_required_validator(
                    step.key,
                    tr(
                        "Bitte fülle die Pflichtfelder aus, bevor du fortfährst.",
                        "Please complete the required fields before continuing.",
                        lang=lang,
                    ),
                )
                if step.required_fields
                else None,
            )
            for step in WIZARD_STEPS
        ]
        required_map = {step.key: step.required_fields for step in WIZARD_STEPS if step.required_fields}
    wiz = Wizard(WIZARD_ID, steps)
    for step_key, required_fields in required_map.items():
        missing_required = [path for path in required_fields if not _has_value(profile, path)]
        st.session_state[wiz.k("required", step_key)] = "" if missing_required else "ok"
    return wiz


def _sync_display_wizard(wiz: Wizard, active_keys: Sequence[str]) -> None:
    target = st.session_state.get(StateKeys.WIZARD_LAST_STEP)
    if isinstance(target, str) and active_keys:
        resolved = resolve_nearest_active_step_key(target, active_keys)
        target = resolved or active_keys[0]
    elif active_keys:
        target = active_keys[0]
    if isinstance(target, str):
        wiz.goto(target, push_history=False)


def _mark_saved_if_profile_changed(wiz: Wizard) -> str:
    saved_key = wiz.k("saved")
    checksum_key = wiz.k("_profile_checksum")
    profile = st.session_state.get(StateKeys.PROFILE)
    checksum = _profile_checksum(profile if isinstance(profile, Mapping) else {})
    previous = st.session_state.get(checksum_key)
    if isinstance(previous, str) and previous != checksum:
        wiz.mark_saved(saved_key)
    st.session_state[checksum_key] = checksum
    return saved_key


inject_global_css()
inject_layout_stability_css()
inject_wizard_uxkit_css(enable_form_fade=USE_FORM_PANEL_FADE)
inject_chatkit_script()
legacy_stepper.STEP_NAVIGATION_ENABLED = False

sidebar_plan = sidebar.render_sidebar(
    logo_asset=APP_LOGO_IMAGE or APP_LOGO_BUFFER,
    logo_data_uri=APP_LOGO_DATA_URI,
    defer=True,
)

lang = st.session_state.get("lang", "de")
profile = st.session_state.get(StateKeys.PROFILE)
profile_data = profile if isinstance(profile, Mapping) else {}
active_keys = resolve_active_step_keys(profile_data, st.session_state)
origin_wiz = _build_display_wizard(active_keys, lang, profile_data)
_sync_display_wizard(origin_wiz, active_keys)
origins_key = origin_wiz.k("_origins")
st.session_state.setdefault(StateKeys.WIZARD_ORIGINS_KEY, origins_key)
st.session_state.setdefault(origins_key, {})

stepper_slot = st.container()
context_slot = st.container()
progress_slot = st.container()
saved_slot = st.container()

if USE_FORM_PANEL_FADE:
    with st.form(key=origin_wiz.k("form", origin_wiz.current_step().id, origin_wiz.state["nonce"])):
        run_wizard()
else:
    run_wizard()

lang = st.session_state.get("lang", "de")
profile = st.session_state.get(StateKeys.PROFILE)
profile_data = profile if isinstance(profile, Mapping) else {}
active_keys = resolve_active_step_keys(profile_data, st.session_state)
display_wiz = _build_display_wizard(active_keys, lang, profile_data)
_sync_display_wizard(display_wiz, active_keys)
saved_key = _mark_saved_if_profile_changed(display_wiz)

legend = tr("🔎 extrahiert · 🤖 vorgeschlagen", "🔎 extracted · 🤖 suggested", lang=lang)
with stepper_slot:
    render_stepper(display_wiz)
with context_slot:
    render_context_bar(display_wiz, legend_right=legend)
with progress_slot:
    render_progress_and_microcopy(display_wiz)
with saved_slot:
    render_saved_badge_if_recent(display_wiz, saved_key)

sidebar.render_sidebar(
    logo_asset=APP_LOGO_IMAGE or APP_LOGO_BUFFER,
    logo_data_uri=APP_LOGO_DATA_URI,
    plan=sidebar_plan,
)
