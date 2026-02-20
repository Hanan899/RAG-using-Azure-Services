"""HTTP client utilities for calling the backend API."""

from typing import Any, Dict, List, Tuple

import requests


def send_chat(
    backend_url: str,
    message: str,
    history: List[Dict[str, str]],
    top_k: int = 5,
) -> Tuple[str, List[Dict[str, Any]]]:
    """Send a chat request to the backend and return the answer and sources."""

    payload = {
        "message": message,
        "history": history,
        "top_k": top_k,
    }
    response = requests.post(f"{backend_url}/api/chat", json=payload, timeout=60)
    response.raise_for_status()
    data = response.json()
    return data.get("answer", ""), data.get("sources", [])
