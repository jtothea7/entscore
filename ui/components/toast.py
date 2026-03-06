"""
Toast notification wrapper
"""
import streamlit as st


def show_success(message: str):
    """Show a success toast."""
    st.toast(message, icon="✅")


def show_error(message: str):
    """Show an error toast."""
    st.toast(message, icon="❌")


def show_warning(message: str):
    """Show a warning toast."""
    st.toast(message, icon="⚠️")


def show_info(message: str):
    """Show an info toast."""
    st.toast(message, icon="ℹ️")
