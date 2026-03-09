"""
Settings page: DataForSEO config, cache management, API cost display
"""
import streamlit as st
import os
from dotenv import load_dotenv, set_key

from core.validators import validate_dataforseo_credentials, get_credentials
from core.cache import Cache
from core.api_tracker import APITracker
from db.database import get_connection, init_database, get_api_usage_total
from ui.components.toast import show_success, show_error


def _is_cloud_deployment() -> bool:
    """Detect if running on HF Spaces or Streamlit Cloud."""
    return bool(os.getenv("SPACE_ID") or os.getenv("STREAMLIT_SHARING_MODE"))


def render_settings_page():
    """Render the settings page."""
    st.header("Settings")

    # DataForSEO credentials
    st.subheader("DataForSEO API")

    load_dotenv()
    current_login, current_password = get_credentials()
    current_login = current_login or ""
    current_password = current_password or ""

    has_creds = bool(current_login and current_password)
    if has_creds:
        # Mask the email — only show first 3 chars
        masked = current_login[:3] + "***" if len(current_login) > 3 else "***"
        st.success(f"Credentials configured for: {masked}")
    else:
        st.warning("No DataForSEO credentials configured.")

    if _is_cloud_deployment():
        st.info(
            "Credentials are managed via environment secrets. "
            "Update them in your HF Spaces or Streamlit Cloud dashboard."
        )
    else:
        with st.expander("Update Credentials"):
            login = st.text_input("Login (email)", value="")
            password = st.text_input("Password", type="password", value="")

            if st.button("Save & Test Credentials"):
                if not login or not password:
                    show_error("Both login and password are required.")
                else:
                    with st.spinner("Testing credentials..."):
                        is_valid, error = validate_dataforseo_credentials(login, password)

                    if is_valid:
                        env_path = os.path.join(
                            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                            ".env",
                        )
                        set_key(env_path, "DATAFORSEO_LOGIN", login)
                        set_key(env_path, "DATAFORSEO_PASSWORD", password)
                        show_success("Credentials saved and verified!")
                        st.rerun()
                    else:
                        show_error("Credential test failed. Check your login and password.")

    st.divider()

    # API usage / cost tracking
    st.subheader("API Usage")

    conn = get_connection()
    try:
        usage_30d = get_api_usage_total(conn, days=30)
        usage_7d = get_api_usage_total(conn, days=7)
    finally:
        conn.close()

    cols = st.columns(2)
    cols[0].metric("Last 7 Days", f"${usage_7d['total_cost']:.4f}", f"{usage_7d['call_count']} calls")
    cols[1].metric("Last 30 Days", f"${usage_30d['total_cost']:.4f}", f"{usage_30d['call_count']} calls")

    st.divider()

    # Cache management
    st.subheader("Cache Management")

    cache = Cache()

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Clear Expired Cache"):
            cache.clear_expired()
            show_success("Expired cache entries removed.")

    with col2:
        if st.button("Clear All Cache", type="secondary"):
            cache.clear_all()
            show_success("All cache cleared.")

    st.divider()

    # Database
    st.subheader("Database")

    if st.button("Initialize / Reset Database"):
        init_database()
        show_success("Database initialized.")

    st.caption(
        "Database location: `data/entscore.db` | "
        "Cache and analysis data are stored locally."
    )
