"""
GSC-driven page opportunity ranking (audit queue).

Upload a GSC CSV -> see all pages sorted by optimization opportunity ->
click any row to auto-populate analyze page.
"""
import streamlit as st
import pandas as pd

from core.gsc_importer import parse_gsc_csv
from db.database import get_connection, save_gsc_data, get_gsc_data
from ui.components.empty_state import render_empty_state
from ui.components.toast import show_success, show_error


def render_audit_queue_page():
    """Render the GSC audit queue page."""
    st.header("Page Audit Queue")
    st.markdown(
        "Upload a Google Search Console CSV export to find your biggest optimization opportunities."
    )

    # Upload section
    uploaded_file = st.file_uploader(
        "Upload GSC CSV",
        type=["csv"],
        help="Export from Google Search Console > Performance > Export",
    )

    if uploaded_file:
        try:
            records, warnings = parse_gsc_csv(uploaded_file)

            if warnings:
                for w in warnings:
                    st.warning(w)

            # Save to database
            conn = get_connection()
            try:
                save_gsc_data(conn, records)
            finally:
                conn.close()

            show_success(f"Imported {len(records)} records from GSC CSV.")

        except ValueError as e:
            show_error(str(e))
        except Exception as e:
            show_error(f"Failed to parse CSV: {str(e)}")

    st.divider()

    # Display audit queue
    conn = get_connection()
    try:
        gsc_records = get_gsc_data(conn, limit=100)
    finally:
        conn.close()

    if not gsc_records:
        render_empty_state(
            title="No GSC Data",
            message="Upload a Google Search Console CSV to see your page optimization opportunities.",
            icon="chart",
        )
        return

    # Build dataframe
    df = pd.DataFrame(gsc_records)
    display_df = df[
        ["keyword", "url", "clicks", "impressions", "ctr", "position", "opportunity_score"]
    ].copy()

    display_df["ctr"] = display_df["ctr"].apply(lambda x: f"{x:.1%}")
    display_df["position"] = display_df["position"].apply(lambda x: f"{x:.1f}")
    display_df["opportunity_score"] = display_df["opportunity_score"].apply(
        lambda x: f"{x:.1f}"
    )

    display_df.columns = [
        "Keyword", "URL", "Clicks", "Impressions", "CTR", "Position", "Opportunity"
    ]

    st.markdown(f"**{len(display_df)} pages** sorted by optimization opportunity:")

    # Render as dataframe with selection
    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        height=500,
    )

    st.divider()

    # Quick-analyze from queue
    st.subheader("Analyze from Queue")
    st.markdown("Select a keyword and URL from the table above, or enter them manually:")

    keywords = df["keyword"].unique().tolist()
    urls = df["url"].unique().tolist()

    col1, col2 = st.columns(2)
    with col1:
        selected_keyword = st.selectbox("Keyword", options=[""] + keywords)
    with col2:
        selected_url = st.selectbox("URL", options=[""] + [u for u in urls if u])

    if st.button("Analyze This Page", type="primary", disabled=not (selected_keyword and selected_url)):
        st.session_state["prefill_url"] = selected_url
        st.session_state["prefill_keyword"] = selected_keyword
        st.session_state["current_page"] = "analyze"
        st.rerun()

    # Opportunity score explanation
    with st.expander("How is Opportunity Score calculated?"):
        st.markdown(
            """
            **Opportunity Score = Impressions x (1 - CTR) x (1 / Position)**

            Pages with **high impressions**, **low CTR**, and **poor position** are the
            biggest opportunities. These are pages Google already shows to users, but that
            aren't getting clicks — optimizing them has the highest potential ROI.
            """
        )
