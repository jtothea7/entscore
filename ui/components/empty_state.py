"""
Empty/first-run state components
"""
import streamlit as st


def render_empty_state(
    title: str = "No data yet",
    message: str = "Run an analysis to see results here.",
    icon: str = "search",
):
    """Render an empty state placeholder."""
    st.markdown(
        f"""
        <div style="text-align: center; padding: 3rem 1rem; color: #94A3B8;">
            <div style="font-size: 3rem; margin-bottom: 1rem;">
                {"🔍" if icon == "search" else "📊" if icon == "chart" else "📋" if icon == "list" else "⚙️"}
            </div>
            <h3 style="color: #475569; margin-bottom: 0.5rem;">{title}</h3>
            <p>{message}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_first_run():
    """Render the first-run welcome state."""
    render_empty_state(
        title="Welcome to EntScore",
        message="Enter a URL and target keyword to start your first analysis.",
        icon="search",
    )
