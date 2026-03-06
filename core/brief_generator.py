"""
Compiles analysis results into a comprehensive optimization brief
"""
import json
from typing import Dict, Optional
from datetime import datetime

from prompts.optimization_brief import (
    BRIEF_TEMPLATE,
    format_priority_actions,
    format_entity_list,
    format_headings,
)
from prompts.style_instructions import generate_style_instructions
from db.database import get_connection, get_analysis, get_previous_analysis
from core.logger import setup_logger

logger = setup_logger(__name__)


def generate_brief(analysis_id: int) -> str:
    """
    Generate a full optimization brief from a stored analysis.

    Args:
        analysis_id: The analysis ID to generate a brief for

    Returns:
        Formatted markdown brief string
    """
    conn = get_connection()
    try:
        analysis = get_analysis(conn, analysis_id)
        if not analysis:
            return "Error: Analysis not found."

        extra = analysis.get("extra_data", {})
        if isinstance(extra, str):
            try:
                extra = json.loads(extra)
            except (json.JSONDecodeError, TypeError):
                extra = {}

        entities = analysis.get("entities", [])
        competitors = analysis.get("competitors", [])

        # Previous analysis comparison
        previous = get_previous_analysis(
            conn, analysis["url"], analysis["keyword"], analysis_id
        )
        if previous:
            prev_score = previous.get("health_score", 0)
            current_score = analysis.get("health_score", 0)
            delta = current_score - prev_score
            sign = "+" if delta >= 0 else ""
            previous_score_line = (
                f"- **Previous Score:** {prev_score:.0f}/100 "
                f"({sign}{delta:.0f} change)"
            )
        else:
            previous_score_line = ""

        # Build priority actions
        actions = _build_priority_actions(analysis, entities, extra)

        # Style section
        client_style = extra.get("client_style", {})
        competitor_style = extra.get("competitor_style", {})
        style_section = generate_style_instructions(client_style, competitor_style)

        # Heading recommendations
        heading_result = extra.get("heading_result", {})
        heading_issues = heading_result.get("issues", [])
        if heading_issues:
            heading_recommendations = "\n".join(f"- {issue}" for issue in heading_issues)
        else:
            heading_recommendations = "Your heading structure looks good!"

        # Additional recommendations
        additional = []

        # Schema
        client_schema = extra.get("client_schema_types", [])
        comp_schema = extra.get("competitor_schema_frequency", {})
        if not client_schema and comp_schema:
            most_common = max(comp_schema.items(), key=lambda x: x[1])
            additional.append(
                f"- **Add Schema Markup:** {most_common[0]} schema is used by "
                f"{most_common[1]}/10 competitors. You have no schema markup."
            )

        # Internal links
        client_links = extra.get("client_internal_links", 0)
        comp_avg_links = extra.get("competitor_avg_internal_links", 0)
        if comp_avg_links > client_links + 3:
            additional.append(
                f"- **Internal Links:** Increase from {client_links} to "
                f"~{int(comp_avg_links)} (competitor average)."
            )

        # Images
        img_count = extra.get("client_images_count", 0)
        img_alt = extra.get("client_images_with_alt", 0)
        if img_count > 0 and img_alt < img_count:
            additional.append(
                f"- **Image Alt Text:** {img_alt}/{img_count} images have alt text. "
                f"Add descriptive alt text to all images."
            )

        additional_text = "\n".join(additional) if additional else "No additional recommendations."

        # Brand phrases
        brand_phrases = extra.get("brand_phrases", [])
        if brand_phrases:
            brand_section = "Preserve these brand-specific phrases when rewriting:\n"
            brand_section += "\n".join(f'- "{p}"' for p in brand_phrases)
        else:
            brand_section = "No brand-specific phrases detected."

        # Competitor summary
        comp_lines = []
        for comp in competitors[:10]:
            status = "scraped" if comp.get("scrape_success") else "failed"
            pos = comp.get("position", "?")
            wc = comp.get("word_count", 0)
            comp_lines.append(
                f"| #{pos} | {comp['url'][:60]}{'...' if len(comp['url']) > 60 else ''} | {wc:,} words | {status} |"
            )

        competitor_summary = "| Pos | URL | Words | Status |\n|-----|-----|-------|--------|\n"
        competitor_summary += "\n".join(comp_lines) if comp_lines else "No competitor data."

        # Format the brief
        brief = BRIEF_TEMPLATE.format(
            url=analysis["url"],
            keyword=analysis["keyword"],
            health_score=analysis.get("health_score", 0),
            previous_score_line=previous_score_line,
            priority_actions=format_priority_actions(actions),
            client_word_count=analysis.get("client_word_count", 0),
            competitor_avg_word_count=analysis.get("competitor_avg_word_count", 0),
            recommended_min=analysis.get("recommended_word_count_min", 0),
            recommended_max=analysis.get("recommended_word_count_max", 0),
            missing_entities_section=format_entity_list(entities, "missing"),
            weak_entities_section=format_entity_list(entities, "weak"),
            client_headings_section=format_headings(
                extra.get("client_headings", [])
            ),
            heading_recommendations=heading_recommendations,
            style_section=style_section,
            additional_recommendations=additional_text,
            brand_phrases_section=brand_section,
            competitor_summary=competitor_summary,
            duration=analysis.get("analysis_duration_seconds", 0),
            cost=0.0,  # TODO: sum from api_usage table
        )

        logger.info(f"Generated brief for analysis {analysis_id}")
        return brief

    finally:
        conn.close()


def _build_priority_actions(analysis: Dict, entities: list, extra: Dict) -> list:
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

    # Heading issues (HIGH if missing H2s)
    heading_issues = extra.get("heading_result", {}).get("issues", [])
    for issue in heading_issues[:2]:
        actions.append({
            "priority": "HIGH",
            "action": issue,
            "reason": "Heading structure issue detected",
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

    return actions[:8]  # Max 8
