"""Session history page for reviewing conversation context."""

from __future__ import annotations

import streamlit as st

from components.chat_component import render_chat_history
from utils.state import initialize_state
from utils.ui import inject_global_styles, render_page_header, render_sidebar_nav
from utils.view_models import build_history_stats

st.set_page_config(page_title="Session History · RAG Chatbot", layout="wide")
inject_global_styles()
render_sidebar_nav("Session History")
initialize_state(st.session_state)

render_page_header(
    "Session History",
    "Review the current session conversation and activity.",
)

messages = st.session_state.get("messages", [])
stats = build_history_stats(messages)

metric_cols = st.columns(3)
metric_cols[0].metric("Total Messages", stats["total"])
metric_cols[1].metric("User Messages", stats["user"])
metric_cols[2].metric("Assistant Messages", stats["assistant"])

st.divider()

if messages:
    render_chat_history(messages)
else:
    st.info("No session history yet. Start chatting to see messages here.")
