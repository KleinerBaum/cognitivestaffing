from pathlib import Path
import base64
import streamlit as st

# --- Page defaults (title + favicon work across pages) ---
st.set_page_config(
    page_title="Vacalyser — AI Recruitment",
    page_icon="images/logo_icon.png",  # or emoji like "🤖"
    layout="wide",
)  # st.set_page_config is the official way to set title/icon/layout.  # :contentReference[oaicite:6]{index=6}

# --- Brand: show logo above the navigation (app + sidebar) ---
st.logo(
    "images/color1_logo_transparent_background.png",  # your horizontal logo
    icon_image="images/color1_logo_transparent_background.png",  # small square icon when sidebar collapsed
    link="https://github.com/KleinerBaum/cognitivestaffing",
)  # st.logo renders in the upper-left of app and sidebar.  # :contentReference[oaicite:7]{index=7}

# --- Load the futuristic CSS ---
css_path = Path("styles/vacalyser.css")
st.markdown(css_path.read_text(), unsafe_allow_html=True)

# --- Inject background image as a CSS variable (base64) ---
bg_path = Path("images/AdobeStock_506577005.jpeg")
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
        st.Page("pages/Advantages.py", title="Advantages", icon=":sparkles:"),
        st.Page(
            "pages/Tech_Overview.py", title="Tech Overview", icon=":material/route:"
        ),
    ]
)  # st.Page/st.navigation lets you set page labels and icons explicitly.  # :contentReference[oaicite:8]{index=8}

pg.run()
