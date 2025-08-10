from __future__ import annotations
import streamlit as st
import streamlit.components.v1 as components

# Minimal Tailwind injector:
# - Loads Tailwind CDN inside the component iframe
# - Best-effort injection into the parent document's <head> so native Streamlit widgets get Tailwind variables
# Note: This is a pragmatic approach; Streamlit's DOM is not guaranteed stable.
def inject_tailwind(theme: str = "dark") -> None:
    html = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
  (function() {{
    try {{
      const parentDoc = window.parent.document;

      // Inject tailwind CDN into parent if not already present
      if (!parentDoc.getElementById('tailwind-cdn')) {{
        const s = parentDoc.createElement('script');
        s.src = 'https://cdn.tailwindcss.com';
        s.id = 'tailwind-cdn';
        parentDoc.head.appendChild(s);
      }}

      // Ensure a dark class if requested
      if ('{theme}' === 'dark') {{
        parentDoc.documentElement.classList.add('dark');
      }} else {{
        parentDoc.documentElement.classList.remove('dark');
      }}

      // Basic theme variables (optional)
      const styleId = 'vacalyser-theme-vars';
      if (!parentDoc.getElementById(styleId)) {{
        const st = parentDoc.createElement('style');
        st.id = styleId;
        st.innerHTML = `
          :root {{
            --bg-app: #0b0f14;
            --bg-card: #111827;
            --fg-muted: #9ca3af;
            --fg: #e5e7eb;
            --primary: #22d3ee; /* cyan-400 */
            --accent: #a78bfa;  /* violet-400 */
          }}
          .dark body, .dark .stApp {{
            background-color: var(--bg-app) !important;
            color: var(--fg) !important;
          }}
          .dark .stButton > button {{
            background: linear-gradient(135deg, var(--primary), var(--accent));
            color: #0c1116;
            border: none;
            border-radius: 10px;
            font-weight: 600;
          }}
          .dark .stButton > button:hover {{
            filter: brightness(0.95);
          }}
          .dark .stTextInput > div > div input,
          .dark textarea,
          .dark select {{
            background-color: var(--bg-card) !important;
            color: var(--fg) !important;
            border: 1px solid #1f2937 !important;
          }}
        `;
        parentDoc.head.appendChild(st);
      }}
    }} catch (e) {{
      // no-op
    }}
  }})();
  </script>
</head>
<body></body>
</html>
"""
    # Render zero-height component that runs the injection
    components.html(html, height=0, width=0, scrolling=False)
