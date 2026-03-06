"""
Style instruction templates based on formality score + markers
"""


def generate_style_instructions(
    client_style: dict, competitor_style: dict
) -> str:
    """
    Generate style instructions for the optimization brief.

    Args:
        client_style: Client's style analysis dict
        competitor_style: Average competitor style dict

    Returns:
        Formatted style instruction string
    """
    lines = []

    formality = client_style.get("formality", 0.5)
    markers = client_style.get("markers", [])
    grade = client_style.get("readability_grade", 0)
    ease = client_style.get("flesch_reading_ease", 0)
    avg_sent = client_style.get("avg_sentence_length", 0)

    # Formality description
    if formality >= 0.75:
        formality_desc = "Formal"
    elif formality >= 0.5:
        formality_desc = "Moderately formal"
    elif formality >= 0.25:
        formality_desc = "Conversational"
    else:
        formality_desc = "Casual"

    lines.append(
        f"**Current Tone:** {formality_desc} (formality: {formality:.2f})"
    )

    if markers:
        lines.append(f"**Style Markers:** {', '.join(markers)}")

    lines.append(f"**Reading Level:** Grade {grade:.1f} (Flesch ease: {ease:.0f}/100)")
    lines.append(f"**Average Sentence Length:** {avg_sent:.1f} words")

    # Competitor comparison
    if competitor_style:
        comp_formality = competitor_style.get("formality", 0.5)
        comp_grade = competitor_style.get("readability_grade", 0)
        comp_sent = competitor_style.get("avg_sentence_length", 0)

        lines.append("")
        lines.append("### Competitor Comparison")

        if abs(formality - comp_formality) > 0.15:
            if formality > comp_formality:
                lines.append(
                    f"- Your tone is more formal than competitors "
                    f"(you: {formality:.2f}, them: {comp_formality:.2f}). "
                    f"Consider a slightly more conversational approach."
                )
            else:
                lines.append(
                    f"- Your tone is more casual than competitors "
                    f"(you: {formality:.2f}, them: {comp_formality:.2f}). "
                    f"Consider a slightly more professional approach."
                )

        if abs(grade - comp_grade) > 2:
            if grade > comp_grade:
                lines.append(
                    f"- Your reading level is higher (grade {grade:.1f} vs {comp_grade:.1f}). "
                    f"Consider simplifying for broader accessibility."
                )
            else:
                lines.append(
                    f"- Your reading level is lower (grade {grade:.1f} vs {comp_grade:.1f}). "
                    f"This may be appropriate depending on your audience."
                )

        if abs(avg_sent - comp_sent) > 4:
            if avg_sent > comp_sent:
                lines.append(
                    f"- Your sentences are longer (avg {avg_sent:.1f} vs {comp_sent:.1f} words). "
                    f"Consider breaking up long sentences for readability."
                )

    # Style recommendations
    lines.append("")
    lines.append("### Style Recommendations")
    lines.append("When rewriting this content:")

    if formality >= 0.6:
        lines.append("- Maintain the professional, authoritative tone")
        lines.append("- Use complete sentences and proper grammar")
    else:
        lines.append("- Keep the conversational, approachable tone")
        lines.append("- Use contractions and direct address where natural")

    if grade > 12:
        lines.append("- Try to reduce reading level to grade 9-11 for broader appeal")
    elif grade < 6:
        lines.append("- Consider adding more detailed, substantive content")

    return "\n".join(lines)
