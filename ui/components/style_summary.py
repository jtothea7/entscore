"""
Writing style display card
"""
import streamlit as st
from typing import Dict


def render_style_summary(client_style: dict, competitor_style: dict = None):
    """
    Render a compact writing style comparison card.
    """
    if not client_style:
        st.info("No style data available.")
        return

    formality = client_style.get("formality", 0.5)
    grade = client_style.get("readability_grade", 0)
    ease = client_style.get("flesch_reading_ease", 0)
    avg_sent = client_style.get("avg_sentence_length", 0)
    markers = client_style.get("markers", [])

    # Formality description
    if formality >= 0.75:
        tone_desc = "Formal"
    elif formality >= 0.5:
        tone_desc = "Moderately Formal"
    elif formality >= 0.25:
        tone_desc = "Conversational"
    else:
        tone_desc = "Casual"

    st.markdown(
        f"""
        <div class="entscore-card">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
                <div>
                    <strong style="font-size: 1.1rem;">Tone: {tone_desc}</strong>
                    <span style="color: #6B7280; margin-left: 0.5rem;">(formality: {formality:.2f})</span>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    cols = st.columns(3)
    cols[0].metric("Reading Grade", f"{grade:.1f}")
    cols[1].metric("Flesch Ease", f"{ease:.0f}/100")
    cols[2].metric("Avg Sentence", f"{avg_sent:.1f} words")

    if markers:
        st.markdown(
            "**Style markers:** " + " · ".join(f"`{m}`" for m in markers)
        )

    # Competitor comparison
    if competitor_style:
        comp_formality = competitor_style.get("formality", 0.5)
        comp_grade = competitor_style.get("readability_grade", 0)

        if abs(formality - comp_formality) > 0.15:
            direction = "more formal" if formality > comp_formality else "more casual"
            st.markdown(
                f"Your tone is **{direction}** than competitors "
                f"(you: {formality:.2f}, them: {comp_formality:.2f})."
            )

        if abs(grade - comp_grade) > 2:
            direction = "higher" if grade > comp_grade else "lower"
            st.markdown(
                f"Your reading level is **{direction}** "
                f"(grade {grade:.1f} vs {comp_grade:.1f})."
            )
