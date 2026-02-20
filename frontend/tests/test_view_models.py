"""Tests for frontend view-model helpers."""

from __future__ import annotations

from frontend.utils.view_models import build_document_stats, build_history_stats


def test_build_document_stats_defaults() -> None:
    """Ensure document stats derive counts when not provided."""

    docs = [
        {"title": "A", "metadata": {"chunk_count": 2}},
        {"title": "B", "metadata": {"chunk_count": 3}},
    ]
    stats = build_document_stats(docs)
    assert stats["file_count"] == 2
    assert stats["chunk_count"] == 5
    assert stats["chart_data"][0]["title"] == "A"


def test_build_document_stats_override_counts() -> None:
    """Ensure provided counts override derived values."""

    docs = [{"title": "A", "metadata": {"chunk_count": 2}}]
    stats = build_document_stats(docs, file_count=10, chunk_count=99)
    assert stats["file_count"] == 10
    assert stats["chunk_count"] == 99


def test_build_history_stats() -> None:
    """Ensure history stats count roles correctly."""

    messages = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
        {"role": "user", "content": "help"},
    ]
    stats = build_history_stats(messages)
    assert stats["total"] == 3
    assert stats["user"] == 2
    assert stats["assistant"] == 1
