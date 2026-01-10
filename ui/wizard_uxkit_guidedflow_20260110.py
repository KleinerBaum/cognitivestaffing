# ui/wizard_uxkit_guidedflow_20260110.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Sequence, Tuple, Literal
import html
import time
import uuid

import streamlit as st


# ---------- Types ----------
Origin = Literal["extracted", "suggested", "manual"]


# ---------- Constants ----------
_WIZARD_STATE_KEY = "_wizard_uxkit_state_v20260110"
_CSS_FLAG_KEY = "_wiz_uxkit_css_v20260110_injected"

_KEYCAP = {
    1: "1️⃣",
    2: "2️⃣",
    3: "3️⃣",
    4: "4️⃣",
    5: "5️⃣",
    6: "6️⃣",
    7: "7️⃣",
    8: "8️⃣",
    9: "9️⃣",
    10: "🔟",
}


def _esc(s: str) -> str:
    return html.escape(s, quote=True)


# ---------- CSS ----------
def inject_wizard_uxkit_css(*, enable_form_fade: bool = False) -> None:
    """
    Inject compact CSS used by this wizard kit.

    Notes
    -----
    - enable_form_fade=False (default): no global animation for Streamlit forms.
    - enable_form_fade=True: adds a CSS rule that animates *all* Streamlit forms
      (div[data-testid="stForm"]). Use this only if your wizard is the only (or main)
      st.form usage in the app.
    """
    if st.session_state.get(_CSS_FLAG_KEY):
        return

    form_fade_css = ""
    if enable_form_fade:
        form_fade_css = """
/* Optional: fade step panel by fading Streamlit's form wrapper */
div[data-testid="stForm"]{ animation: wizFade .25s ease; transform-origin: top; }
"""

    st.markdown(
        f"""
<style>
/* ===== Wizard Stepper ===== */
.wiz-stepper{{
  display:flex;
  gap:.5rem;
  flex-wrap:wrap;
  align-items:center;
  margin:.25rem 0 1rem;
}}
.wiz-step{{
  padding:.28rem .62rem;
  border-radius:999px;
  border:1px solid rgba(128,128,128,.35);
  background: rgba(0,0,0,.02);
  opacity:.55;
  transition: opacity .2s ease, transform .2s ease, box-shadow .2s ease;
  user-select:none;
  white-space:nowrap;
}}
.wiz-step.active{{
  opacity:1;
  transform: translateY(-1px);
  box-shadow: 0 1px 6px rgba(0,0,0,.08);
}}
.wiz-step.done{{ opacity:.85; }}

/* ===== Context Bar ===== */
.wiz-bar{{
  display:flex;
  justify-content:space-between;
  align-items:flex-end;
  gap:1rem;
  margin:.25rem 0 .5rem;
}}
.wiz-bar .left{{ font-size:.92rem; opacity:.85; }}
.wiz-bar .right{{ font-size:.92rem; opacity:.75; text-align:right; }}

/* ===== Origin badges (🔎 / 🤖 / ✍️) ===== */
.wiz-origin{{
  display:inline-block;
  padding:.08rem .42rem;
  margin-left:.4rem;
  border-radius:999px;
  border:1px solid rgba(128,128,128,.25);
  font-size:.82rem;
  opacity:.9;
}}
.wiz-origin.extracted::before{{ content:"🔎 "; }}
.wiz-origin.suggested::before{{ content:"🤖 "; }}
.wiz-origin.manual::before{{ content:"✍️ "; }}

/* ===== Fade-In (200–300ms) ===== */
.wiz-fade{{ animation: wizFade .25s ease; transform-origin: top; }}
@keyframes wizFade{{
  from{{ opacity:0; transform: translateY(4px); }}
  to{{ opacity:1; transform:none; }}
}}

/* ===== Inline Saved Badge ===== */
.wiz-saved{{
  display:inline-block;
  margin-left:.5rem;
  font-size:.92rem;
  opacity:.85;
  animation: wizSaved .15s ease;
}}
@keyframes wizSaved{{
  from{{ opacity:0; transform: translateY(2px); }}
  to{{ opacity:.85; transform:none; }}
}}

{form_fade_css}

/* ===== Accessibility ===== */
@media (prefers-reduced-motion: reduce){{
  .wiz-step, .wiz-fade, .wiz-saved, div[data-testid="stForm"]{{
    animation:none !important;
    transition:none !important;
  }}
}}
</style>
        """,
        unsafe_allow_html=True,
    )
    st.session_state[_CSS_FLAG_KEY] = True


# ---------- Core data structures ----------
@dataclass(frozen=True)
class WizardStep:
    """
    Minimal step definition.

    - validate: blocks "Next" when (ok=False) and returns an error message.
    - visible_if: if provided, the step is skipped when it returns False.
    - next_step_id: optional branching hook (step-graph). Return:
        - a step id (string) to jump to
        - None to fall back to linear order
    """

    id: str
    label: str
    title: str
    render: Callable[["Wizard"], None]

    validate: Optional[Callable[["Wizard"], Tuple[bool, str]]] = None
    visible_if: Optional[Callable[["Wizard"], bool]] = None
    next_step_id: Optional[Callable[["Wizard"], Optional[str]]] = None


class Wizard:
    """
    Streamlit wizard controller with:

    - Multi-wizard safe state (namespaced under _wizard_uxkit_state_v20260110 + wizard_id)
    - Stable widget key builder: wiz.k(...)
    - Branching (step graph) via step.next_step_id + a history stack for Back
    - visible_if skipping
    - Gentle validation stop on Next (errors stored per-step; no popups)
    - Visited tracking to mark steps "done" in the stepper
    """

    def __init__(self, wizard_id: str, steps: Sequence[WizardStep]):
        if not steps:
            raise ValueError("Wizard needs at least 1 step.")
        self.wizard_id = wizard_id
        self._all_steps = list(steps)

        ids = [s.id for s in self._all_steps]
        if len(set(ids)) != len(ids):
            raise ValueError(f"WizardStep ids must be unique. Got: {ids}")

        self._ensure_state()

    # ----- State -----
    def _ensure_state(self) -> None:
        root = st.session_state.setdefault(_WIZARD_STATE_KEY, {})
        ws = root.setdefault(self.wizard_id, {})

        first_id = self._all_steps[0].id
        ws.setdefault("current_step_id", first_id)
        ws.setdefault("nonce", uuid.uuid4().hex)
        ws.setdefault("saved_at", {})  # widget_key -> ts
        ws.setdefault("errors", {})  # step_id -> msg
        ws.setdefault("history", [])  # stack of step_ids (for Back in branching)
        ws.setdefault("visited", [first_id])  # ordered list of visited step_ids

    @property
    def state(self) -> dict:
        return st.session_state[_WIZARD_STATE_KEY][self.wizard_id]

    # ----- Namespaced widget keys -----
    def k(self, *parts: str) -> str:
        """
        Stable widget key builder.

        Example:
            key = wiz.k("role", "title")  ->  "wiz:<wizard_id>:role:title"
        """
        return "wiz:" + self.wizard_id + ":" + ":".join(parts)

    # ----- Steps (with visible_if filtering) -----
    def active_steps(self) -> list[WizardStep]:
        active: list[WizardStep] = []
        for s in self._all_steps:
            if s.visible_if is None or s.visible_if(self):
                active.append(s)
        return active or self._all_steps

    def step_ids(self, *, active_only: bool = True) -> list[str]:
        steps = self.active_steps() if active_only else self._all_steps
        return [s.id for s in steps]

    def step_by_id(self, step_id: str, *, active_only: bool = True) -> Optional[WizardStep]:
        steps = self.active_steps() if active_only else self._all_steps
        for s in steps:
            if s.id == step_id:
                return s
        return None

    def current_step(self) -> WizardStep:
        active = self.active_steps()
        cur_id = self.state["current_step_id"]
        for s in active:
            if s.id == cur_id:
                return s
        # Current step became invisible -> snap to first visible
        self.goto(active[0].id, push_history=False)
        return active[0]

    def current_index(self) -> int:
        active = self.active_steps()
        cur_id = self.state["current_step_id"]
        for i, s in enumerate(active):
            if s.id == cur_id:
                return i
        return 0

    # ----- Navigation -----
    def goto(self, step_id: str, *, push_history: bool = False) -> None:
        active_ids = self.step_ids(active_only=True)
        if step_id not in active_ids:
            step_id = active_ids[0]

        cur = self.state["current_step_id"]
        if step_id == cur:
            return

        if push_history:
            self.state["history"].append(cur)

        self.state["current_step_id"] = step_id
        self.state["nonce"] = uuid.uuid4().hex

        # visited tracking (ordered)
        visited: list[str] = self.state.get("visited", [])
        if step_id not in visited:
            visited.append(step_id)
        self.state["visited"] = visited

        # Clear error for the step we just left (gentle stop UX)
        self.state["errors"].pop(cur, None)

    def prev(self) -> None:
        hist: list[str] = self.state.get("history", [])
        if hist:
            target = hist.pop()
            self.state["history"] = hist
            self.goto(target, push_history=False)
            return

        # Fallback linear back (if no history)
        active = self.active_steps()
        idx = self.current_index()
        if idx > 0:
            self.goto(active[idx - 1].id, push_history=False)

    def next(self) -> bool:
        cur_step = self.current_step()
        ok, msg = self._validate_step(cur_step)

        if not ok:
            self.state["errors"][cur_step.id] = msg
            return False

        # Clear error on success even if we remain on same step (e.g., last step)
        self.state["errors"].pop(cur_step.id, None)

        # Branching hook
        target_id: Optional[str] = None
        if cur_step.next_step_id is not None:
            target_id = cur_step.next_step_id(self)

        # Fallback to linear order
        if not target_id:
            active = self.active_steps()
            idx = self.current_index()
            if idx < len(active) - 1:
                target_id = active[idx + 1].id

        if target_id:
            self.goto(target_id, push_history=True)

        return True

    def _validate_step(self, step: WizardStep) -> Tuple[bool, str]:
        if step.validate is None:
            return True, ""
        return step.validate(self)

    # ----- Errors -----
    def error_for_current_step(self) -> str:
        return self.state.get("errors", {}).get(self.current_step().id, "")

    # ----- Saved micro-feedback -----
    def mark_saved(self, widget_key: str) -> None:
        self.state["saved_at"][widget_key] = time.time()

    def recently_saved(self, widget_key: str, *, within_s: float = 1.8) -> bool:
        t = self.state["saved_at"].get(widget_key)
        return bool(t and (time.time() - t) <= within_s)

    # ----- Progress -----
    def progress_pct(self, *, mode: Literal["index", "visited"] = "index") -> int:
        active = self.active_steps()
        if len(active) <= 1:
            return 100

        if mode == "visited":
            visited = set(self.state.get("visited", []))
            visited_count = len([s for s in active if s.id in visited])
            return int((visited_count / len(active)) * 100)

        idx = self.current_index()
        return int((idx / (len(active) - 1)) * 100)

    # ----- Reset -----
    def reset(self) -> None:
        """
        Reset this wizard's state (keeps the wizard_id namespace).
        """
        first_id = self._all_steps[0].id
        self.state.update(
            {
                "current_step_id": first_id,
                "nonce": uuid.uuid4().hex,
                "saved_at": {},
                "errors": {},
                "history": [],
                "visited": [first_id],
            }
        )


# ---------- Validation helpers ----------
def validate_required(widget_key: str, msg: str) -> Callable[[Wizard], Tuple[bool, str]]:
    """
    Common validation: require non-empty string / value in st.session_state[widget_key].
    """

    def _v(_wiz: Wizard) -> Tuple[bool, str]:
        val = st.session_state.get(widget_key)
        ok = bool(val and str(val).strip())
        return ok, ("" if ok else msg)

    return _v


# ---------- UI helpers ----------
def render_stepper(wiz: Wizard) -> None:
    active = wiz.active_steps()
    cur_id = wiz.current_step().id
    visited = set(wiz.state.get("visited", []))

    parts = ['<div class="wiz-stepper">']
    for i, s in enumerate(active, start=1):
        cls = ["wiz-step"]
        if s.id == cur_id:
            cls.append("active")
        elif s.id in visited:
            cls.append("done")

        keycap = _KEYCAP.get(i, f"{i}.")
        parts.append(f'<span class="{" ".join(cls)}">{keycap}&nbsp;{_esc(s.label)}</span>')
    parts.append("</div>")

    st.markdown("\n".join(parts), unsafe_allow_html=True)


def render_context_bar(
    wiz: Wizard,
    *,
    legend_right: str = "🔎 extrahiert · 🤖 vorgeschlagen",
) -> None:
    active = wiz.active_steps()
    idx = wiz.current_index() + 1
    total = len(active)
    step_label = active[idx - 1].label

    nonce = wiz.state["nonce"]
    left = _esc(f"Schritt {idx}/{total} · {step_label} 👇")
    right = _esc(legend_right)

    st.markdown(
        f"""
<div class="wiz-bar wiz-fade" id="wiz-bar-{nonce}">
  <div class="left">{left}</div>
  <div class="right">{right}</div>
</div>
        """,
        unsafe_allow_html=True,
    )


def render_saved_badge_if_recent(wiz: Wizard, widget_key: str, *, within_s: float = 1.8) -> None:
    if wiz.recently_saved(widget_key, within_s=within_s):
        st.markdown("<span class='wiz-saved'>✅ gespeichert</span>", unsafe_allow_html=True)


def origin_badge_html(origin: Origin) -> str:
    origin_norm = origin if origin in ("extracted", "suggested", "manual") else "manual"
    label = {
        "extracted": "extrahiert",
        "suggested": "vorgeschlagen",
        "manual": "manuell",
    }[origin_norm]
    return f"<span class='wiz-origin {origin_norm}'>{_esc(label)}</span>"


def render_field_label(
    label: str,
    *,
    origin: Optional[Origin] = None,
    right_hint: Optional[str] = None,
    help_text: Optional[str] = None,
) -> None:
    """
    Render a label row with an optional origin badge (🔎/🤖/✍️) and a right-side hint.

    Usage pattern (no duplicated labels):
        render_field_label("Jobtitel", origin="suggested", right_hint="optional")
        st.text_input("Jobtitel", label_visibility="collapsed", key=wiz.k("role","title"))

    """
    badge = origin_badge_html(origin) if origin else ""
    right = f"<span style='opacity:.7;font-size:.9rem'>{_esc(right_hint)}</span>" if right_hint else ""
    help_html = (
        f"<div style='opacity:.75;font-size:.9rem;margin-top:.15rem'>{_esc(help_text)}</div>" if help_text else ""
    )

    st.markdown(
        f"""
<div class="wiz-fade" style="display:flex;justify-content:space-between;gap:1rem;align-items:baseline;">
  <div><strong>{_esc(label)}</strong>{badge}</div>
  <div>{right}</div>
</div>
{help_html}
        """,
        unsafe_allow_html=True,
    )


def render_progress_and_microcopy(
    wiz: Wizard,
    *,
    mode: Literal["index", "visited"] = "index",
    est_seconds_per_step: int = 20,
    done_caption: str = "Fast geschafft 🚀",
) -> None:
    pct = wiz.progress_pct(mode=mode)
    st.progress(pct)

    active = wiz.active_steps()
    if mode == "visited":
        st.caption("Noch ein paar Klicks – du bist fast da 🚀")
        return

    remaining_steps = max(0, len(active) - (wiz.current_index() + 1))
    remaining_sec = remaining_steps * est_seconds_per_step
    if remaining_sec <= 15:
        st.caption(done_caption)
    else:
        mins = max(1, int(round(remaining_sec / 60)))
        st.caption(f"Noch ~{mins} Minute{'n' if mins != 1 else ''} – du bist fast da 🚀")
