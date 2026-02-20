"""Settings page for tuning chat parameters."""

from __future__ import annotations

import os

import streamlit as st
from dotenv import load_dotenv

from utils.api_client import ApiClientError, check_health
from utils.state import initialize_state, update_settings
from utils.ui import inject_global_styles, render_page_header, render_sidebar_nav

load_dotenv()

BACKEND_URL = os.getenv("BACKEND_URL", "https://ragchatbotbackend.azurewebsites.net")

st.set_page_config(page_title="Settings · RAG Chatbot", layout="wide")
inject_global_styles()
render_sidebar_nav("Settings")
initialize_state(st.session_state)

render_page_header(
    "Settings",
    "Adjust response behavior and retrieval parameters.",
)

st.subheader("Model Controls")
current_temp = st.slider("Temperature", 0.0, 1.0, st.session_state.temperature, 0.05)
current_max_tokens = st.slider(
    "Max tokens", 100, 2000, st.session_state.max_tokens, 50
)
current_top_k = st.slider("Top K", 1, 10, st.session_state.top_k, 1)

update_settings(
    st.session_state, current_temp, current_max_tokens, current_top_k
)

st.divider()
st.subheader("Diagnostics")
if st.button("Check Health"):
    try:
        status = check_health(BACKEND_URL)
        st.success(
            f"Search: {status.get('azure_search')} | OpenAI: {status.get('azure_openai')}"
        )
    except ApiClientError:
        st.error("Health check failed")
