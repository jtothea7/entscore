"""
Past analyses list (history page)
"""
import streamlit as st
import pandas as pd
from datetime import datetime

from db.database import get_connection, get_analysis_history
from ui.components.empty_state import render_empty_state
from ui.theme import get_score_color


def render_history_page():
    """Render the analysis history page."""
    st.header("Analysis History")

    conn = get_connection()
    try:
        analyses = get_analysis_history(conn, limit=50)
    finally:
        conn.close()

    if not analyses:
        render_empty_state(
            title="No analyses yet",
            message="Run your first analysis from the Analyze page.",
            icon="list",
        )
        return

    st.markdown(f"**{len(analyses)}** past analyses:")

    # Build display table
    for analysis in analyses:
        score = analysis.get("health_score", 0)
        score_color = get_score_color(score)
        created = analysis.get("created_at", "")
        if isinstance(created, str) and created:
            try:
                dt = datetime.fromisoformat(created)
                created = dt.strftime("%b %d, %Y %I:%M %p")
            except (ValueError, TypeError):
                pass

        col1, col2, col3, col4 = st.columns([1, 3, 2, 1])

        with col1:
            st.markdown(
                f'<div style="font-size: 1.5rem; font-weight: 700; color: {score_color}; text-align: center;">{score:.0f}</div>',
                unsafe_allow_html=True,
            )

        with col2:
            st.markdown(f"**{analysis.get('keyword', '')}**")
            st.caption(analysis.get("url", "")[:80])

        with col3:
            st.caption(f"{analysis.get('domain', '')} | {created}")
            st.caption(
                f"{analysis.get('competitors_analyzed', 0)} competitors | "
                f"{analysis.get('analysis_duration_seconds', 0):.1f}s"
            )

        with col4:
            if st.button("View", key=f"view_{analysis['id']}"):
                st.session_state["analysis_id"] = analysis["id"]
                st.session_state["current_page"] = "results"
                st.rerun()

        st.divider()
