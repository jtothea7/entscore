"""
Competitor list with metrics (accordion panels)
"""
import streamlit as st
from typing import List, Dict


def render_competitor_panel(competitors: list, serp_data: dict = None):
    """
    Render competitor details as expandable accordion panels.

    Args:
        competitors: List of competitor dicts from DB
        serp_data: Optional dict mapping URL to SERP data
    """
    if not competitors:
        st.info("No competitor data available.")
        return

    successful = [c for c in competitors if c.get("scrape_success")]
    failed = [c for c in competitors if not c.get("scrape_success")]

    st.markdown(
        f"**{len(successful)}** competitors analyzed"
        + (f", **{len(failed)}** failed" if failed else "")
    )

    # Sort by position
    sorted_comps = sorted(
        competitors,
        key=lambda c: c.get("position") or 999,
    )

    for comp in sorted_comps:
        url = comp.get("url", "Unknown")
        position = comp.get("position", "?")
        success = comp.get("scrape_success", False)

        status_icon = "✅" if success else "❌"
        label = f"#{position} — {url[:70]}{'...' if len(url) > 70 else ''} {status_icon}"

        with st.expander(label):
            if success:
                cols = st.columns(3)
                cols[0].metric("Word Count", f"{comp.get('word_count', 0):,}")
                cols[1].metric("Headings", comp.get("heading_count", 0))
                cols[2].metric("Scrape Method", comp.get("scrape_method", "-"))
            else:
                st.warning(
                    f"Could not scrape this page. Method: {comp.get('scrape_method', 'unknown')}"
                )
