"""Session state helpers for the Streamlit app."""

from __future__ import annotations

from typing import Any, Dict


def initialize_state(state: Dict[str, Any]) -> None:
    """Initialize session state defaults."""

    state.setdefault("messages", [])
    state.setdefault("temperature", 0.2)
    state.setdefault("max_tokens", 512)
    state.setdefault("top_k", 5)


def update_settings(
    state: Dict[str, Any],
    temperature: float,
    max_tokens: int,
    top_k: int,
) -> None:
    """Update settings in session state."""

    state["temperature"] = temperature
    state["max_tokens"] = max_tokens
    state["top_k"] = top_k
