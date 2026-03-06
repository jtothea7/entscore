"""
EntScore — SEO Page Optimization Tool
Streamlit multipage app entry point
"""
import streamlit as st
import sys
import os
import ssl
import nltk

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Ensure NLTK data is available (needed by textstat for readability scores)
try:
    nltk.data.find("corpora/cmudict")
except LookupError:
    try:
        ssl._create_default_https_context = ssl._create_unverified_context
    except AttributeError:
        pass
    nltk.download("cmudict", quiet=True)

from ui.custom_css import inject_custom_css
from ui.pages.analyze import render_analyze_page
from ui.pages.results import render_results_page
from ui.pages.audit_queue import render_audit_queue_page
from ui.pages.history import render_history_page
from ui.pages.settings import render_settings_page
from db.database import init_database

# Page config
st.set_page_config(
    page_title="EntScore",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Inject custom CSS
inject_custom_css()

# Initialize database on first run
init_database()

# Initialize session state
if "current_page" not in st.session_state:
    st.session_state["current_page"] = "analyze"

# Sidebar navigation
with st.sidebar:
    st.markdown("## EntScore")
    st.caption("SEO Page Optimization")
    st.divider()

    pages = {
        "analyze": "Analyze",
        "results": "Results",
        "audit_queue": "Audit Queue",
        "history": "History",
        "settings": "Settings",
    }

    for key, label in pages.items():
        icon = {
            "analyze": "🔍",
            "results": "📊",
            "audit_queue": "📋",
            "history": "🕐",
            "settings": "⚙️",
        }.get(key, "")

        if st.button(
            f"{icon} {label}",
            key=f"nav_{key}",
            use_container_width=True,
            type="primary" if st.session_state["current_page"] == key else "secondary",
        ):
            st.session_state["current_page"] = key
            st.rerun()

    st.divider()
    st.caption("v1.0.0")

# Route to current page
current_page = st.session_state["current_page"]

if current_page == "analyze":
    render_analyze_page()
elif current_page == "results":
    render_results_page()
elif current_page == "audit_queue":
    render_audit_queue_page()
elif current_page == "history":
    render_history_page()
elif current_page == "settings":
    render_settings_page()
