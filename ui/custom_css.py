"""
Global CSS injection for Streamlit
"""
import streamlit as st
from ui.theme import (
    PRIMARY, BG_PRIMARY, BG_CARD, TEXT_PRIMARY, TEXT_SECONDARY,
    BORDER_LIGHT, RADIUS_MD, SPACING_MD,
)


def inject_custom_css():
    """Inject global CSS styles into the Streamlit app."""
    st.markdown(
        f"""
        <style>
        /* Global styles */
        .main .block-container {{
            max-width: 1100px;
            padding-top: 2rem;
        }}

        /* Card component */
        .entscore-card {{
            background: {BG_CARD};
            border: 1px solid {BORDER_LIGHT};
            border-radius: {RADIUS_MD};
            padding: {SPACING_MD};
            margin-bottom: {SPACING_MD};
        }}

        /* Score gauge */
        .score-gauge {{
            text-align: center;
            padding: 1.5rem;
        }}

        .score-value {{
            font-size: 3rem;
            font-weight: 700;
            line-height: 1;
        }}

        .score-label {{
            color: {TEXT_SECONDARY};
            font-size: 0.875rem;
            margin-top: 0.25rem;
        }}

        /* Priority action item */
        .priority-item {{
            padding: 12px;
            border-radius: 4px;
            margin-bottom: 8px;
            background: #F9FAFB;
        }}

        .priority-high {{
            border-left: 3px solid #EF4444;
        }}

        .priority-medium {{
            border-left: 3px solid #F59E0B;
        }}

        .priority-low {{
            border-left: 3px solid #10B981;
        }}

        /* Entity table */
        .entity-missing {{
            background-color: #FEF2F2;
        }}

        .entity-weak {{
            background-color: #FFFBEB;
        }}

        .entity-strong {{
            background-color: #ECFDF5;
        }}

        /* Gap status badges */
        .badge {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 0.75rem;
            font-weight: 600;
        }}

        .badge-missing {{
            background: #FEE2E2;
            color: #991B1B;
        }}

        .badge-weak {{
            background: #FEF3C7;
            color: #92400E;
        }}

        .badge-strong {{
            background: #D1FAE5;
            color: #065F46;
        }}

        /* Sidebar styling */
        .css-1d391kg {{
            padding-top: 1rem;
        }}

        /* Hide Streamlit branding */
        #MainMenu {{visibility: hidden;}}
        footer {{visibility: hidden;}}

        /* Brief container */
        .brief-container {{
            background: {BG_CARD};
            border: 1px solid {BORDER_LIGHT};
            border-radius: {RADIUS_MD};
            padding: 1.5rem;
            max-height: 600px;
            overflow-y: auto;
        }}

        /* Metric card */
        .metric-card {{
            background: {BG_CARD};
            border: 1px solid {BORDER_LIGHT};
            border-radius: {RADIUS_MD};
            padding: 1rem;
            text-align: center;
        }}

        .metric-value {{
            font-size: 1.5rem;
            font-weight: 700;
            color: {TEXT_PRIMARY};
        }}

        .metric-label {{
            font-size: 0.8rem;
            color: {TEXT_SECONDARY};
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
