"""API client for interacting with the backend services."""

from __future__ import annotations

from typing import Any, Dict, Generator, List, Tuple

import requests


class ApiClientError(RuntimeError):
    """Raised when an API call fails."""


def _extract_error_detail(response: requests.Response) -> str:
    """Extract a readable error detail from backend responses."""

    try:
        payload = response.json()
    except ValueError:
        payload = None

    if isinstance(payload, dict):
        detail = payload.get("detail")
        if isinstance(detail, str) and detail.strip():
            return detail.strip()
        if detail is not None:
            return str(detail)
    if response.text:
        return response.text
    return f"Request failed with status {response.status_code}"


def send_chat_message(
    backend_url: str,
    message: str,
    history: List[Dict[str, str]],
    temperature: float,
    max_tokens: int,
    top_k: int = 5,
) -> Tuple[str, List[Dict[str, Any]], int, bool, List[str] | None]:
    """Send a chat request and return answer, sources, and token usage."""

    payload = {
        "message": message,
        "history": history,
        "top_k": top_k,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    response = requests.post(f"{backend_url}/api/chat", json=payload, timeout=60)
    if not response.ok:
        raise ApiClientError(_extract_error_detail(response))
    data = response.json()
    return (
        data.get("answer", ""),
        data.get("sources", []),
        data.get("tokens_used", 0),
        data.get("has_sufficient_context", True),
        data.get("suggested_actions"),
    )


def stream_chat_message(
    backend_url: str,
    message: str,
    history: List[Dict[str, str]],
    temperature: float,
    max_tokens: int,
    top_k: int = 5,
) -> Generator[str, None, None]:
    """Stream chat response chunks from the backend via SSE."""

    payload = {
        "message": message,
        "history": history,
        "top_k": top_k,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    response = requests.post(
        f"{backend_url}/api/chat/stream", json=payload, stream=True, timeout=60
    )
    if not response.ok:
        raise ApiClientError(_extract_error_detail(response))

    for line in response.iter_lines(decode_unicode=True):
        if not line:
            continue
        if line.startswith("data:"):
            chunk = line[len("data:"):]
            if chunk.startswith(" "):
                chunk = chunk[1:]
            if chunk == "[DONE]":
                continue
            yield chunk


def upload_document(backend_url: str, filename: str, file_bytes: bytes) -> Dict[str, Any]:
    """Upload a document for indexing."""

    files = {"file": (filename, file_bytes)}
    response = requests.post(
        f"{backend_url}/api/documents/upload", files=files, timeout=120
    )
    if not response.ok:
        raise ApiClientError(_extract_error_detail(response))
    return response.json()


def list_documents(backend_url: str) -> Dict[str, Any]:
    """List documents from the backend index."""

    response = requests.get(f"{backend_url}/api/documents", timeout=60)
    if not response.ok:
        raise ApiClientError(_extract_error_detail(response))
    return response.json()


def delete_document(backend_url: str, document_id: str) -> Dict[str, Any]:
    """Delete a document by ID."""

    response = requests.delete(
        f"{backend_url}/api/documents/{document_id}", timeout=60
    )
    if not response.ok:
        raise ApiClientError(_extract_error_detail(response))
    return response.json()


def check_health(backend_url: str) -> Dict[str, Any]:
    """Check backend health status."""

    response = requests.get(f"{backend_url}/api/health", timeout=30)
    if not response.ok:
        raise ApiClientError(_extract_error_detail(response))
    return response.json()
