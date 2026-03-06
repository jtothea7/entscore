"""
Priority action items component - THE most important section of results page
"""
import streamlit as st
from typing import List, Dict
import json

from ui.theme import get_priority_color


def render_priority_actions(analysis: dict, entities: list, extra: dict):
    """
    Generate and display 5-8 ranked priority actions.

    Actions ranked by impact:
        HIGH: Missing critical entities (9-10/10 competitors)
        HIGH: Major word count gap (>40% below average)
        HIGH: Heading structure problems
        MEDIUM: Missing common entities (6-8/10 competitors)
        MEDIUM: Schema markup missing
        LOW: Internal link count
        LOW: Image alt text
    """
    st.subheader("Priority Actions")
    st.markdown("*Take these actions in order. Highest impact first.*")

    actions = _build_actions(analysis, entities, extra)

    if not actions:
        st.success("No major optimization opportunities detected. Your page is well-optimized!")
        return

    for i, action in enumerate(actions[:8], 1):
        priority = action["priority"]
        color = get_priority_color(priority)

        priority_emoji = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(priority, "⚪")

        st.markdown(
            f"""
            <div class="priority-item priority-{priority.lower()}">
                <strong>{i}. [{priority_emoji} {priority}]</strong> {action['action']}<br>
                <span style="color: #6B7280; font-size: 14px;">{action['reason']}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _build_actions(analysis: dict, entities: list, extra: dict) -> list:
    """Build ranked priority action list."""
    actions = []

    # Missing critical entities (HIGH)
    critical_missing = [
        e for e in entities
        if e.get("gap_status") == "missing" and e.get("competitor_frequency", 0) >= 9
    ]
    for ent in critical_missing[:3]:
        actions.append({
            "priority": "HIGH",
            "action": f'Add "{ent["entity_text"]}"',
            "reason": f"Missing from your page, found in {ent['competitor_frequency']}/10 competitors",
        })

    # Word count gap (HIGH if >40%)
    client_wc = analysis.get("client_word_count", 0)
    comp_avg_wc = analysis.get("competitor_avg_word_count", 0)
    if comp_avg_wc > 0:
        gap_pct = ((comp_avg_wc - client_wc) / comp_avg_wc) * 100
        if gap_pct > 40:
            actions.append({
                "priority": "HIGH",
                "action": f"Increase word count from {client_wc:,} to ~{int(comp_avg_wc):,}",
                "reason": f"You're {int(gap_pct)}% below competitor average",
            })

    # Heading issues
    heading_result = extra.get("heading_result", {})
    for issue in heading_result.get("issues", [])[:2]:
        actions.append({
            "priority": "HIGH",
            "action": issue,
            "reason": "Heading structure issue",
        })

    # Missing common entities (MEDIUM)
    common_missing = [
        e for e in entities
        if e.get("gap_status") == "missing" and 6 <= e.get("competitor_frequency", 0) < 9
    ]
    for ent in common_missing[:3]:
        actions.append({
            "priority": "MEDIUM",
            "action": f'Add "{ent["entity_text"]}"',
            "reason": f"Found in {ent['competitor_frequency']}/10 competitors",
        })

    # Schema markup (MEDIUM)
    client_schema = extra.get("client_schema_types", [])
    comp_schema = extra.get("competitor_schema_frequency", {})
    if not client_schema and comp_schema:
        most_common = max(comp_schema.items(), key=lambda x: x[1])
        actions.append({
            "priority": "MEDIUM",
            "action": f"Add {most_common[0]} schema markup",
            "reason": f"{most_common[1]}/10 competitors have it, you have none",
        })

    # Internal links (LOW)
    client_links = extra.get("client_internal_links", 0)
    comp_avg_links = extra.get("competitor_avg_internal_links", 0)
    if comp_avg_links > client_links + 3:
        actions.append({
            "priority": "LOW",
            "action": f"Increase internal links from {client_links} to ~{int(comp_avg_links)}",
            "reason": f"Competitor average is {comp_avg_links:.1f}",
        })

    # Image alt text (LOW)
    img_count = extra.get("client_images_count", 0)
    img_alt = extra.get("client_images_with_alt", 0)
    if img_count > 0 and img_alt < img_count:
        actions.append({
            "priority": "LOW",
            "action": "Add alt text to images",
            "reason": f"You have {img_alt}/{img_count} images with alt text",
        })

    return actions
