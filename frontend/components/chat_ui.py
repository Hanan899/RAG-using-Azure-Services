"""Reusable chat UI rendering helpers."""

from typing import List, Dict

import streamlit as st


def render_chat(messages: List[Dict[str, str]]) -> None:
    """Render chat messages in the Streamlit chat layout."""

    for message in messages:
        role = message.get("role", "assistant")
        content = message.get("content", "")
        # Use Streamlit's chat message container for consistent styling.
        with st.chat_message(role):
            st.markdown(content)
