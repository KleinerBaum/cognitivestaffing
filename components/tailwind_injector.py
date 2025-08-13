"""Utility to inject TailwindCSS and basic theming variables into Streamlit.

The function toggles between a dark and light theme by manipulating the
parent document's stylesheet. This keeps styling centralised while allowing
runtime theme switching.
"""

from __future__ import annotations

import streamlit.components.v1 as components


def inject_tailwind(theme: str = "dark") -> None:
    """Inject Tailwind CSS and theme variables into the Streamlit app."""

    dark_vars = """
          :root {
            --bg-app: #0b0f14;
            --bg-card: #111827;
            --fg-muted: #9ca3af;
            --fg: #e5e7eb;
            --primary: #22d3ee;
            --accent: #a78bfa;
          }
          body, .stApp {
            background-color: var(--bg-app) !important;
            color: var(--fg) !important;
          }
          .stButton > button {
            background: linear-gradient(135deg, var(--primary), var(--accent));
            color: #0c1116;
            border: none;
            border-radius: 10px;
            font-weight: 600;
          }
          .stButton > button:hover { filter: brightness(0.95); }
          .stTextInput > div > div input,
          textarea,
          select {
            background-color: var(--bg-card) !important;
            color: var(--fg) !important;
            border: 1px solid #1f2937 !important;
          }
    """

    light_vars = """
          :root {
            --bg-app: #ffffff;
            --bg-card: #f9fafb;
            --fg-muted: #6b7280;
            --fg: #111827;
            --primary: #0ea5e9;
            --accent: #6366f1;
          }
          body, .stApp {
            background-color: var(--bg-app) !important;
            color: var(--fg) !important;
          }
          .stButton > button {
            background: linear-gradient(135deg, var(--primary), var(--accent));
            color: #fff;
            border: none;
            border-radius: 10px;
            font-weight: 600;
          }
          .stButton > button:hover { filter: brightness(0.95); }
          .stTextInput > div > div input,
          textarea,
          select {
            background-color: var(--bg-card) !important;
            color: var(--fg) !important;
            border: 1px solid #d1d5db !important;
          }
    """

    css_vars = dark_vars if theme == "dark" else light_vars

    html = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset=\"utf-8\" />
  <script src=\"https://cdn.tailwindcss.com\"></script>
  <script>
  (function() {{
    try {{
      const parentDoc = window.parent.document;
      if (!parentDoc.getElementById('tailwind-cdn')) {{
        const s = parentDoc.createElement('script');
        s.src = 'https://cdn.tailwindcss.com';
        s.id = 'tailwind-cdn';
        parentDoc.head.appendChild(s);
      }}
      parentDoc.documentElement.classList.toggle('dark', '{theme}' === 'dark');
      const styleId = 'vacalyser-theme-vars';
      let st = parentDoc.getElementById(styleId);
      if (!st) {{
        st = parentDoc.createElement('style');
        st.id = styleId;
        parentDoc.head.appendChild(st);
      }}
      st.innerHTML = `{css_vars}`;
    }} catch (e) {{}}
  }})();
  </script>
</head>
<body></body>
</html>
"""
    components.html(html, height=0, width=0, scrolling=False)
