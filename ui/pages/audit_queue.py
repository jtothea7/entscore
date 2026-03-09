"""
GSC-driven page opportunity ranking (audit queue).

Upload GSC Queries CSV and/or Pages CSV -> see opportunities sorted by score ->
pick a URL + keyword combo to auto-populate the analyze page.
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
        "Upload your Google Search Console CSV exports to find your biggest optimization opportunities."
    )

    # Two file uploaders side by side
    col1, col2 = st.columns(2)

    with col1:
        queries_file = st.file_uploader(
            "Queries CSV",
            type=["csv"],
            help="GSC > Performance > Export > Queries",
            key="gsc_queries",
        )

    with col2:
        pages_file = st.file_uploader(
            "Pages CSV",
            type=["csv"],
            help="GSC > Performance > Export > Pages",
            key="gsc_pages",
        )

    # Process uploads
    if queries_file:
        try:
            records, warnings, csv_type = parse_gsc_csv(queries_file)
            for w in warnings:
                st.warning(w)
            conn = get_connection()
            try:
                save_gsc_data(conn, records, source_type="queries")
            finally:
                conn.close()
            show_success(f"Imported {len(records)} keywords from Queries CSV.")
        except (ValueError, Exception) as e:
            show_error(f"Queries CSV error: {str(e)}")

    if pages_file:
        try:
            records, warnings, csv_type = parse_gsc_csv(pages_file)
            for w in warnings:
                st.warning(w)
            conn = get_connection()
            try:
                save_gsc_data(conn, records, source_type="pages")
            finally:
                conn.close()
            show_success(f"Imported {len(records)} pages from Pages CSV.")
        except (ValueError, Exception) as e:
            show_error(f"Pages CSV error: {str(e)}")

    st.divider()

    # Load data
    conn = get_connection()
    try:
        query_records = get_gsc_data(conn, source_type="queries", limit=200)
        page_records = get_gsc_data(conn, source_type="pages", limit=200)
    finally:
        conn.close()

    if not query_records and not page_records:
        render_empty_state(
            title="No GSC Data",
            message="Upload your GSC Queries and Pages CSV files to see optimization opportunities.",
            icon="chart",
        )
        return

    # Pages table
    if page_records:
        st.subheader("Page Opportunities")
        st.caption("Pages with high impressions but low CTR and poor position — your biggest wins.")

        pages_df = pd.DataFrame(page_records)
        display_pages = pages_df[["url", "clicks", "impressions", "ctr", "position", "opportunity_score"]].copy()
        display_pages["ctr"] = display_pages["ctr"].apply(lambda x: f"{x:.1%}")
        display_pages["position"] = display_pages["position"].apply(lambda x: f"{x:.1f}")
        display_pages["opportunity_score"] = display_pages["opportunity_score"].apply(lambda x: f"{x:.1f}")
        display_pages.columns = ["URL", "Clicks", "Impressions", "CTR", "Position", "Opportunity"]

        st.dataframe(display_pages, use_container_width=True, hide_index=True, height=350)

    # Queries table
    if query_records:
        st.subheader("Keyword Opportunities")
        st.caption("Keywords where you're getting impressions but not clicks — optimize these pages.")

        queries_df = pd.DataFrame(query_records)
        display_queries = queries_df[["keyword", "clicks", "impressions", "ctr", "position", "opportunity_score"]].copy()
        display_queries["ctr"] = display_queries["ctr"].apply(lambda x: f"{x:.1%}")
        display_queries["position"] = display_queries["position"].apply(lambda x: f"{x:.1f}")
        display_queries["opportunity_score"] = display_queries["opportunity_score"].apply(lambda x: f"{x:.1f}")
        display_queries.columns = ["Keyword", "Clicks", "Impressions", "CTR", "Position", "Opportunity"]

        st.dataframe(display_queries, use_container_width=True, hide_index=True, height=350)

    st.divider()

    # Quick-analyze from queue
    st.subheader("Analyze from Queue")
    st.markdown("Pick a URL and keyword from the tables above, then hit Analyze.")

    # Build dropdown options
    url_options = []
    if page_records:
        url_options = [r["url"] for r in page_records if r.get("url")]

    keyword_options = []
    if query_records:
        keyword_options = [r["keyword"] for r in query_records if r.get("keyword")]

    col1, col2 = st.columns(2)
    with col1:
        selected_url = st.selectbox("URL", options=[""] + url_options)
    with col2:
        selected_keyword = st.selectbox("Keyword", options=[""] + keyword_options)

    if st.button("Analyze This Page", type="primary", disabled=not (selected_keyword and selected_url)):
        st.session_state["prefill_url"] = selected_url
        st.session_state["prefill_keyword"] = selected_keyword
        st.session_state["current_page"] = "analyze"
        st.rerun()

    # Explanation
    with st.expander("How is Opportunity Score calculated?"):
        st.markdown(
            """
            **Opportunity Score = Impressions x (1 - CTR) x (1 / Position)**

            Pages/keywords with **high impressions**, **low CTR**, and **poor position**
            are the biggest opportunities. These are already being shown by Google but
            aren't getting clicks — optimizing them has the highest potential ROI.
            """
        )
