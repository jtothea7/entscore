"""
HOME PAGE: URL + keyword input -> analyze

This is the primary entry point for EntScore. Users paste a URL and keyword,
choose location and page type, hit Analyze, and get routed to the results page.
"""
import streamlit as st
import os
from dotenv import load_dotenv

from core.validators import validate_url, validate_keyword, get_credentials
from core.gap_analyzer import run_analysis
from core.dataforseo_client import DataForSEOClient
from ui.components.empty_state import render_first_run
from ui.components.progress_tracker import ProgressTracker
from ui.components.toast import show_error, show_success
from db.database import init_database

# Common US locations for quick selection
DEFAULT_LOCATIONS = [
    {"label": "United States (National)", "code": 2840, "name": "United States"},
    {"label": "New York, NY", "code": 1023191, "name": "New York,New York,United States"},
    {"label": "Los Angeles, CA", "code": 1013962, "name": "Los Angeles,California,United States"},
    {"label": "Chicago, IL", "code": 1016367, "name": "Chicago,Illinois,United States"},
    {"label": "Houston, TX", "code": 1026339, "name": "Houston,Texas,United States"},
    {"label": "Phoenix, AZ", "code": 1023587, "name": "Phoenix,Arizona,United States"},
    {"label": "Miami, FL", "code": 1015116, "name": "Miami,Florida,United States"},
    {"label": "Dallas, TX", "code": 1026135, "name": "Dallas,Texas,United States"},
    {"label": "Atlanta, GA", "code": 1015254, "name": "Atlanta,Georgia,United States"},
    {"label": "Denver, CO", "code": 1014395, "name": "Denver,Colorado,United States"},
    {"label": "Seattle, WA", "code": 1027744, "name": "Seattle,Washington,United States"},
]

PAGE_TYPES = {
    "any": "Any (auto-detect)",
    "service": "Service Page (commercial/transactional)",
    "blog": "Blog Post (informational)",
}


def render_analyze_page():
    """Render the analyze (home) page."""
    st.header("Analyze a Page")
    st.markdown("Enter your page URL and target keyword to get optimization recommendations.")

    # Check for credentials
    load_dotenv()
    cred_login, cred_password = get_credentials()
    has_creds = bool(cred_login and cred_password)

    if not has_creds:
        st.warning(
            "DataForSEO credentials not configured. "
            "Go to **Settings** to add them before running an analysis."
        )

    # Input form
    with st.form("analyze_form"):
        url = st.text_input(
            "Page URL",
            placeholder="https://example.com/your-page",
            help="The page you want to optimize",
            value=st.session_state.get("prefill_url", ""),
        )

        keyword = st.text_input(
            "Target Keyword",
            placeholder="e.g., pest control services",
            help="The keyword you want this page to rank for (10 words max)",
            value=st.session_state.get("prefill_keyword", ""),
        )

        col1, col2 = st.columns(2)

        with col1:
            # Single location field — type any city or pick "National"
            location_input = st.text_input(
                "Search Location",
                placeholder="e.g., Fort Lauderdale, FL (leave blank for national)",
                help="Type a city and state for local results, or leave blank for a national US search.",
            )

        with col2:
            # Page type selection
            page_type = st.selectbox(
                "Page Type",
                options=list(PAGE_TYPES.keys()),
                format_func=lambda x: PAGE_TYPES[x],
                index=0,
                help="Service pages compete against other service pages. Blog posts compete against other blogs. This filters out irrelevant competitors.",
            )

        submitted = st.form_submit_button(
            "Analyze",
            type="primary",
            use_container_width=True,
            disabled=not has_creds,
        )

    if submitted:
        # Clear prefill values
        st.session_state.pop("prefill_url", None)
        st.session_state.pop("prefill_keyword", None)

        # Validate inputs
        url_valid, url_error = validate_url(url)
        if not url_valid:
            show_error(url_error)
            return

        kw_valid, kw_error = validate_keyword(keyword)
        if not kw_valid:
            show_error(kw_error)
            return

        # Resolve location
        location_code = 2840
        location_name = "United States"

        if location_input.strip():
            # Check if it matches a preset first
            input_lower = location_input.strip().lower()
            matched_preset = None
            for loc in DEFAULT_LOCATIONS:
                if loc["label"].lower() == input_lower or loc["name"].lower().startswith(input_lower):
                    matched_preset = loc
                    break

            if matched_preset:
                location_code = matched_preset["code"]
                location_name = matched_preset["name"]
            else:
                # Look up via DataForSEO
                dfs = DataForSEOClient(cred_login, cred_password)

                with st.spinner(f"Looking up location: {location_input}..."):
                    locations = dfs.search_locations(location_input.strip())

                if locations:
                    location_code = locations[0]["location_code"]
                    location_name = locations[0]["location_name"]
                    st.info(f"Location: {location_name}")
                else:
                    show_error(f"Could not find '{location_input}'. Using national (US) search.")

        # Initialize database
        init_database()

        # Run analysis with progress
        progress = ProgressTracker()

        try:
            result = run_analysis(
                url=url.strip(),
                keyword=keyword.strip(),
                location_code=location_code,
                location_name=location_name,
                page_type=page_type,
                progress_callback=progress.update,
            )

            progress.complete()
            show_success(
                f"Analysis complete! Score: {result['health_score']:.0f}/100 "
                f"({result['duration']:.1f}s, ${result['cost']:.4f})"
            )

            # Store analysis_id in session state and navigate to results
            st.session_state["analysis_id"] = result["analysis_id"]
            st.session_state["current_page"] = "results"
            st.rerun()

        except Exception as e:
            progress.error(str(e))
            show_error(f"Analysis failed: {str(e)}")

    # Show first-run state if no previous analyses
    if "analysis_id" not in st.session_state:
        st.divider()
        render_first_run()
