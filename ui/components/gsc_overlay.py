"""
GSC data badges (position, impressions, CTR)
"""
import streamlit as st
from typing import Optional, Dict


def render_gsc_overlay(gsc_data: Optional[Dict] = None):
    """
    Render GSC performance badges if data is available.

    Args:
        gsc_data: Dict with clicks, impressions, ctr, position
    """
    if not gsc_data:
        return

    cols = st.columns(4)

    cols[0].metric(
        "GSC Position",
        f"{gsc_data.get('position', 0):.1f}",
    )
    cols[1].metric(
        "Impressions",
        f"{gsc_data.get('impressions', 0):,}",
    )
    cols[2].metric(
        "Clicks",
        f"{gsc_data.get('clicks', 0):,}",
    )
    cols[3].metric(
        "CTR",
        f"{gsc_data.get('ctr', 0):.1%}",
    )
