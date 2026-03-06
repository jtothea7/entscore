"""
H1-H6 heading structure analysis vs competitors
"""
from typing import Dict, List
from collections import Counter
from core.logger import setup_logger

logger = setup_logger(__name__)


def analyze_headings(headings: List[Dict]) -> Dict:
    """
    Analyze heading structure of a single page.

    Args:
        headings: List of dicts with 'level' and 'text' keys

    Returns:
        Dict with counts per level and structure analysis
    """
    counts = Counter()
    for h in headings:
        counts[h["level"]] += 1

    return {
        "h1": counts.get("h1", 0),
        "h2": counts.get("h2", 0),
        "h3": counts.get("h3", 0),
        "h4": counts.get("h4", 0),
        "h5": counts.get("h5", 0),
        "h6": counts.get("h6", 0),
        "total": sum(counts.values()),
        "headings": headings,
    }


def compare_headings(
    client_headings: List[Dict], competitor_pages: List[Dict]
) -> Dict:
    """
    Compare client heading structure against competitors.

    Args:
        client_headings: Client page headings
        competitor_pages: List of competitor page dicts (must have 'headings' key)

    Returns:
        Dict with client analysis, competitor averages, and score
    """
    client_analysis = analyze_headings(client_headings)

    # Analyze all competitors
    comp_analyses = []
    for page in competitor_pages:
        if page.get("scrape_success") and page.get("headings"):
            comp_analyses.append(analyze_headings(page["headings"]))

    if not comp_analyses:
        return {
            "client": client_analysis,
            "competitor_avg": {},
            "score": 0.5,
            "issues": ["No competitor data available for comparison"],
        }

    # Calculate averages
    comp_avg = {}
    for level in ["h1", "h2", "h3", "h4", "h5", "h6", "total"]:
        values = [ca[level] for ca in comp_analyses]
        comp_avg[level] = round(sum(values) / len(values), 1)

    # Score heading structure (0-1)
    score = 1.0
    issues = []

    # H1 check
    if client_analysis["h1"] == 0:
        score -= 0.3
        issues.append("Missing H1 tag")
    elif client_analysis["h1"] > 1:
        score -= 0.1
        issues.append(f"Multiple H1 tags ({client_analysis['h1']})")

    # H2 check
    if client_analysis["h2"] == 0 and comp_avg.get("h2", 0) > 0:
        score -= 0.3
        issues.append(
            f"No H2 headings (competitors average {comp_avg['h2']:.1f})"
        )
    elif comp_avg.get("h2", 0) > 0:
        h2_ratio = client_analysis["h2"] / comp_avg["h2"]
        if h2_ratio < 0.5:
            score -= 0.2
            issues.append(
                f"Only {client_analysis['h2']} H2s vs competitor avg {comp_avg['h2']:.1f}"
            )

    # Total heading depth
    if client_analysis["total"] == 0:
        score -= 0.2
        issues.append("No headings at all")
    elif comp_avg.get("total", 0) > 0:
        total_ratio = client_analysis["total"] / comp_avg["total"]
        if total_ratio < 0.3:
            score -= 0.1
            issues.append(
                f"Only {client_analysis['total']} total headings vs competitor avg {comp_avg['total']:.1f}"
            )

    score = max(0.0, min(1.0, score))

    logger.info(
        f"Heading analysis: client has {client_analysis['total']} headings, "
        f"competitors avg {comp_avg.get('total', 0):.1f}. Score: {score:.2f}"
    )

    return {
        "client": client_analysis,
        "competitor_avg": comp_avg,
        "competitor_details": comp_analyses,
        "score": round(score, 2),
        "issues": issues,
    }
