from pathlib import Path
import base64
import streamlit as st

BASE_DIR = Path(__file__).parent
IMAGES_DIR = BASE_DIR / "images"

# --- Page defaults (title + favicon work across pages) ---
st.set_page_config(
    page_title="Vacalyser — AI Recruitment",
    page_icon=str(
        IMAGES_DIR / "color1_logo_transparent_background.png"
    ),  # or emoji like "🤖"
)  # st.set_page_config is the official way to set title/icon/layout.  # :contentReference[oaicite:6]{index=6}

# --- Brand: show logo above the navigation (app + sidebar) ---
_logo_path = IMAGES_DIR / "color1_logo_transparent_background.png"
st.logo(
    str(_logo_path),  # your horizontal logo
    icon_image=str(_logo_path),  # small square icon when sidebar collapsed
    link="https://github.com/KleinerBaum/cognitivestaffing",
)  # st.logo renders in the upper-left of app and sidebar.  # :contentReference[oaicite:7]{index=7}

# --- Load the futuristic CSS ---
css_path = BASE_DIR / "styles" / "vacalyser.css"
st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)

# --- Inject background image as a CSS variable (base64) ---
bg_path = IMAGES_DIR / "AdobeStock_506577005.jpeg"
if bg_path.exists():
    b64 = base64.b64encode(bg_path.read_bytes()).decode()
    st.markdown(
        f"<style>:root{{--bg-image: url('data:image/jpeg;base64,{b64}');}}</style>",
        unsafe_allow_html=True,
    )

# --- Define navigation so the first entry is 'Home' and other pages get icons ---
# Adjust file paths/titles to match your repo's scripts in ./pages
pg = st.navigation(
    [
        st.Page("wizard.py", title="Home", icon=":material/home:"),  # your main flow
        st.Page("pages/advantages.py", title="Advantages", icon="✨"),
        st.Page(
            "pages/tech_overview.py", title="Tech Overview", icon=":material/route:"
        ),
    ]
)  # st.Page/st.navigation lets you set page labels and icons explicitly.  # :contentReference[oaicite:8]{index=8}

pg.run()
