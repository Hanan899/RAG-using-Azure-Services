"""Tests for the Streamlit frontend API client utilities."""

from __future__ import annotations

from unittest.mock import MagicMock
import requests

import pytest

from frontend.utils.api_client import (
    ApiClientError,
    check_health,
    send_chat_message,
    stream_chat_message,
    upload_document,
)
from frontend.utils.state import initialize_state, update_settings


def test_api_client_connection(monkeypatch):
    """Verify backend connectivity check."""

    fake_response = MagicMock(ok=True)
    fake_response.json.return_value = {"status": "ok"}
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: fake_response)

    result = check_health("https://ragchatbotbackend.azurewebsites.net")
    assert result["status"] == "ok"


def test_message_sending(monkeypatch):
    """Simulate sending a chat message."""

    fake_response = MagicMock(ok=True)
    fake_response.json.return_value = {"answer": "Hi", "sources": [], "tokens_used": 5}
    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: fake_response)

    answer, sources, tokens, has_context, actions = send_chat_message(
        "https://ragchatbotbackend.azurewebsites.net", "hello", [], 0.2, 512
    )
    assert answer == "Hi"
    assert tokens == 5
    assert has_context is True
    assert actions is None


def test_message_sending_insufficient_context(monkeypatch):
    """Ensure no-context payload is propagated correctly by API client."""

    fake_response = MagicMock(ok=True)
    fake_response.json.return_value = {
        "answer": "I don't have enough information in the knowledge base to answer this question.",
        "sources": [],
        "tokens_used": 3,
        "has_sufficient_context": False,
        "suggested_actions": ["Upload relevant documents"],
    }
    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: fake_response)

    answer, sources, tokens, has_context, actions = send_chat_message(
        "https://ragchatbotbackend.azurewebsites.net", "unknown", [], 0.2, 512
    )
    assert "don't have enough information" in answer
    assert sources == []
    assert tokens == 3
    assert has_context is False
    assert actions == ["Upload relevant documents"]


def test_document_upload(monkeypatch):
    """Test file upload flow."""

    fake_response = MagicMock(ok=True)
    fake_response.json.return_value = {"message": "Document uploaded"}
    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: fake_response)

    result = upload_document("https://ragchatbotbackend.azurewebsites.net", "test.txt", b"hello")
    assert result["message"] == "Document uploaded"


def test_settings_update():
    """Verify settings changes persist in state."""

    state = {}
    initialize_state(state)
    update_settings(state, 0.8, 800, 3)

    assert state["temperature"] == 0.8
    assert state["max_tokens"] == 800
    assert state["top_k"] == 3


def test_error_handling(monkeypatch):
    """Test error handling when backend is unavailable."""

    fake_response = MagicMock(ok=False)
    fake_response.text = "backend down"
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: fake_response)

    with pytest.raises(ApiClientError):
        check_health("https://ragchatbotbackend.azurewebsites.net")


def test_error_handling_prefers_detail_message(monkeypatch):
    """API client should surface backend detail from JSON errors."""

    fake_response = MagicMock(ok=False)
    fake_response.text = "raw error"
    fake_response.json.return_value = {"detail": "Cannot reach Azure Search"}
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: fake_response)

    with pytest.raises(ApiClientError, match="Cannot reach Azure Search"):
        check_health("https://ragchatbotbackend.azurewebsites.net")


def test_streaming_response(monkeypatch):
    """Verify SSE streaming yields chunks."""

    class FakeResponse:
        ok = True

        def iter_lines(self, decode_unicode=True):
            return iter(["data: Hel", "data: lo", "data:  world", ""])

    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: FakeResponse())

    chunks = list(
        stream_chat_message("https://ragchatbotbackend.azurewebsites.net", "hi", [], 0.2, 512, 5)
    )
    assert "".join(chunks) == "Hello world"


def test_sources_toggle():
    """No-op placeholder for removed sources toggle."""

    state = {}
    initialize_state(state)
    update_settings(state, 0.2, 512, 5)
    assert state["top_k"] == 5
