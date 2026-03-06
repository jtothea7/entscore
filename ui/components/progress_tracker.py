"""
Live analysis progress tracker
"""
import streamlit as st


class ProgressTracker:
    """Manages a Streamlit progress bar with step labels."""

    def __init__(self):
        self.container = st.empty()
        self.progress_bar = st.progress(0)
        self.status_text = st.empty()

    def update(self, step: str, progress: float):
        """
        Update progress display.

        Args:
            step: Current step description
            progress: Progress value 0.0 to 1.0
        """
        progress = max(0.0, min(1.0, progress))
        self.progress_bar.progress(progress)
        self.status_text.markdown(f"**{step}**")

    def complete(self):
        """Mark progress as complete and clean up."""
        self.progress_bar.progress(1.0)
        self.status_text.markdown("**Analysis complete!**")

    def error(self, message: str):
        """Show error state."""
        self.progress_bar.empty()
        self.status_text.error(f"Analysis failed: {message}")

    def clear(self):
        """Clear all progress elements."""
        self.container.empty()
        self.progress_bar.empty()
        self.status_text.empty()
