"""
Health score gauge with competitor context
"""
import streamlit as st
from ui.theme import get_score_color, TEXT_SECONDARY


def render_score_card(
    health_score: float,
    entity_coverage: float = 0,
    heading_score: float = 0,
    word_count_score: float = 0,
    readability_score: float = 0,
    link_score: float = 0,
    previous_score: float = None,
    client_word_count: int = 0,
    competitor_avg_word_count: float = 0,
):
    """
    Render the health score card with sub-scores and context.
    """
    score_color = get_score_color(health_score)

    # Score change indicator
    delta_html = ""
    if previous_score is not None:
        delta = health_score - previous_score
        sign = "+" if delta >= 0 else ""
        delta_color = "#10B981" if delta >= 0 else "#EF4444"
        delta_html = f'<div style="color: {delta_color}; font-size: 1rem; font-weight: 600;">{sign}{delta:.0f} from previous</div>'

    # Main score
    st.markdown(
        f"""
        <div class="entscore-card" style="text-align: center; padding: 1.5rem;">
            <div style="font-size: 0.875rem; color: {TEXT_SECONDARY}; text-transform: uppercase; letter-spacing: 0.05em;">Health Score</div>
            <div style="font-size: 3.5rem; font-weight: 700; color: {score_color}; line-height: 1.1;">{health_score:.0f}</div>
            <div style="font-size: 1rem; color: {TEXT_SECONDARY};">/100</div>
            {delta_html}
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Sub-scores
    cols = st.columns(5)

    sub_scores = [
        ("Entity Coverage", entity_coverage),
        ("Headings", heading_score),
        ("Word Count", word_count_score),
        ("Readability", readability_score),
        ("Links", link_score),
    ]

    for col, (label, score) in zip(cols, sub_scores):
        with col:
            color = get_score_color(score)
            st.markdown(
                f"""
                <div class="metric-card">
                    <div class="metric-value" style="color: {color};">{score:.0f}</div>
                    <div class="metric-label">{label}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # Word count context
    if competitor_avg_word_count > 0:
        st.markdown(
            f"""
            <div style="display: flex; justify-content: space-around; padding: 0.75rem; background: #F1F5F9; border-radius: 8px; margin-top: 0.5rem;">
                <div style="text-align: center;">
                    <div style="font-weight: 600;">{client_word_count:,}</div>
                    <div style="font-size: 0.75rem; color: {TEXT_SECONDARY};">Your Words</div>
                </div>
                <div style="text-align: center;">
                    <div style="font-weight: 600;">{competitor_avg_word_count:,.0f}</div>
                    <div style="font-size: 0.75rem; color: {TEXT_SECONDARY};">Competitor Avg</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
