"""Interactive Streamlit frontend for the RAG chatbot."""

from __future__ import annotations

import os

import streamlit as st
from dotenv import load_dotenv

from components.chat_component import render_chat_history, render_message
from utils.api_client import ApiClientError, send_chat_message
from utils.state import initialize_state
from utils.ui import inject_global_styles, render_page_header, render_sidebar_nav

# Load environment variables from a local .env file if present.
load_dotenv()

BACKEND_URL = os.getenv("BACKEND_URL", "https://ragchatbotbackend.azurewebsites.net")

st.set_page_config(page_title="FairWork RAG Chatbot", layout="wide")

inject_global_styles()

initialize_state(st.session_state)

render_sidebar_nav("Chat")

render_page_header(
    "FairWork RAG Chatbot",
    "Ask questions and retrieve answers grounded in your data.",
)

# Main chat container
st.markdown("<div class='chat-container'>", unsafe_allow_html=True)
chat_container = st.container()

with chat_container:
    render_chat_history(st.session_state.messages)

user_input = st.chat_input("Type a message and press Enter...")

if user_input and user_input.strip():
    user_message = {"role": "user", "content": user_input}
    st.session_state.messages.append(user_message)

    with chat_container:
        render_message(user_message)

    full_response = ""
    has_sufficient_context = True
    suggested_actions = None
    tokens_used = 0

    try:
        with st.spinner("Generating response..."):
            (
                answer,
                _sources,
                tokens_used,
                has_sufficient_context,
                suggested_actions,
            ) = send_chat_message(
                BACKEND_URL,
                user_input,
                st.session_state.messages,
                st.session_state.temperature,
                st.session_state.max_tokens,
                st.session_state.top_k,
            )
            full_response = answer
    except ApiClientError as exc:
        error_detail = str(exc).strip()
        st.error(error_detail or "Unable to reach backend. Please try again later.")
        full_response = ""

    if full_response.strip():
        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": full_response,
                "has_sufficient_context": has_sufficient_context,
                "suggested_actions": suggested_actions,
                "tokens_used": tokens_used,
            }
        )
        with chat_container:
            render_message(
                {
                    "role": "assistant",
                    "content": full_response,
                    "has_sufficient_context": has_sufficient_context,
                    "suggested_actions": suggested_actions,
                    "tokens_used": tokens_used,
                }
            )


st.markdown("</div>", unsafe_allow_html=True)
