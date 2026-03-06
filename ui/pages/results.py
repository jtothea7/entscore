"""
Single scrollable results page (merged results + brief).

Sections in order:
1. Score Card + Key Metrics
2. Priority Action Items
3. Entity Gap Table (expandable)
4. Content & Heading Comparison
5. Writing Style Summary
6. Optimization Brief (inline)
7. Competitor Deep Dives (collapsed)
"""
import streamlit as st
import json

from db.database import get_connection, get_analysis, get_previous_analysis
from core.brief_generator import generate_brief
from ui.components.score_card import render_score_card
from ui.components.priority_actions import render_priority_actions
from ui.components.entity_table import render_entity_table
from ui.components.style_summary import render_style_summary
from ui.components.competitor_panel import render_competitor_panel
from ui.components.gsc_overlay import render_gsc_overlay
from ui.components.toast import show_success, show_info


def render_results_page():
    """Render the results page for a completed analysis."""
    analysis_id = st.session_state.get("analysis_id")

    if not analysis_id:
        st.warning("No analysis selected. Go to **Analyze** to run one.")
        return

    # Load analysis from database
    conn = get_connection()
    try:
        analysis = get_analysis(conn, analysis_id)
        if not analysis:
            st.error(f"Analysis {analysis_id} not found.")
            return

        # Parse extra_data
        extra = analysis.get("extra_data", {})
        if isinstance(extra, str):
            try:
                extra = json.loads(extra)
            except (json.JSONDecodeError, TypeError):
                extra = {}

        entities = analysis.get("entities", [])
        competitors = analysis.get("competitors", [])

        # Get previous analysis for comparison
        previous = get_previous_analysis(
            conn, analysis["url"], analysis["keyword"], analysis_id
        )
    finally:
        conn.close()

    # Page header
    st.header(f"Results: {analysis['keyword']}")
    st.caption(f"URL: {analysis['url']}")

    # Re-analyze button
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("Re-Analyze", type="secondary"):
            st.session_state["current_page"] = "analyze"
            st.session_state["prefill_url"] = analysis["url"]
            st.session_state["prefill_keyword"] = analysis["keyword"]
            st.rerun()

    # GSC overlay (if data available)
    gsc_data = extra.get("gsc_data")
    if gsc_data:
        render_gsc_overlay(gsc_data)

    st.divider()

    # SECTION 1: Score Card
    render_score_card(
        health_score=analysis.get("health_score", 0),
        entity_coverage=analysis.get("entity_coverage_score", 0),
        heading_score=analysis.get("heading_score", 0),
        word_count_score=analysis.get("word_count_score", 0),
        readability_score=analysis.get("readability_score", 0),
        link_score=analysis.get("link_score", 0),
        previous_score=previous.get("health_score") if previous else None,
        client_word_count=analysis.get("client_word_count", 0),
        competitor_avg_word_count=analysis.get("competitor_avg_word_count", 0),
    )

    st.divider()

    # SECTION 2: Priority Actions
    render_priority_actions(analysis, entities, extra)

    st.divider()

    # SECTION 3: Entity Gap Table (expandable)
    with st.expander("Entity Gap Analysis", expanded=True):
        show_all = st.checkbox("Show all entities (including strong)", value=False)
        render_entity_table(entities, show_all=show_all)

    # SECTION 4: Content & Heading Comparison
    with st.expander("Content & Heading Comparison"):
        heading_result = extra.get("heading_result", {})

        cols = st.columns(2)

        with cols[0]:
            st.markdown("**Your Page**")
            st.metric("Word Count", f"{analysis.get('client_word_count', 0):,}")

            client_headings = heading_result.get("client", {})
            if client_headings:
                st.markdown(
                    f"H1: {client_headings.get('h1', 0)} | "
                    f"H2: {client_headings.get('h2', 0)} | "
                    f"H3: {client_headings.get('h3', 0)}"
                )

        with cols[1]:
            st.markdown("**Competitor Average**")
            st.metric("Word Count", f"{analysis.get('competitor_avg_word_count', 0):,.0f}")

            comp_avg = heading_result.get("competitor_avg", {})
            if comp_avg:
                st.markdown(
                    f"H1: {comp_avg.get('h1', 0):.1f} | "
                    f"H2: {comp_avg.get('h2', 0):.1f} | "
                    f"H3: {comp_avg.get('h3', 0):.1f}"
                )

        # Heading issues
        issues = heading_result.get("issues", [])
        if issues:
            st.markdown("**Issues:**")
            for issue in issues:
                st.markdown(f"- {issue}")

        # Word count recommendation
        rec_min = analysis.get("recommended_word_count_min", 0)
        rec_max = analysis.get("recommended_word_count_max", 0)
        if rec_min and rec_max:
            st.info(f"Recommended word count: **{rec_min:,} - {rec_max:,}** words")

    # SECTION 5: Writing Style Summary
    with st.expander("Writing Style"):
        client_style = extra.get("client_style", {})
        competitor_style = extra.get("competitor_style", {})
        render_style_summary(client_style, competitor_style)

    st.divider()

    # SECTION 6: Optimization Brief (inline)
    st.subheader("Optimization Brief")

    brief = generate_brief(analysis_id)

    # Copy button
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("Copy Brief to Clipboard", type="primary"):
            try:
                import pyperclip
                pyperclip.copy(brief)
                show_success("Brief copied to clipboard!")
            except Exception:
                show_info("Could not copy to clipboard. Use the text area below to copy manually.")

    with col2:
        # Download button
        st.download_button(
            label="Download Brief (.md)",
            data=brief,
            file_name=f"{analysis['keyword'].replace(' ', '-')}-brief.md",
            mime="text/markdown",
        )

    # Render brief in scrollable container
    st.markdown(
        f'<div class="brief-container">{_markdown_to_html_safe(brief)}</div>',
        unsafe_allow_html=True,
    )

    # Also provide as editable text area
    with st.expander("Edit Brief"):
        st.text_area(
            "Brief text (editable)",
            value=brief,
            height=400,
            key="brief_editor",
        )

    st.divider()

    # SECTION 7: Competitor Deep Dives (collapsed)
    with st.expander("Competitor Details"):
        render_competitor_panel(competitors)

    # Footer
    st.caption(
        f"Analysis completed in {analysis.get('analysis_duration_seconds', 0):.1f}s | "
        f"Competitors: {analysis.get('competitors_analyzed', 0)} analyzed, "
        f"{analysis.get('competitors_failed', 0)} failed"
    )


def _markdown_to_html_safe(text: str) -> str:
    """Minimal markdown to HTML for display in a div."""
    import re
    # Just preserve line breaks and basic formatting
    text = text.replace("\n", "<br>")
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    return text
