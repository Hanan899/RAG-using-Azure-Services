"""View-model helpers for frontend data presentation."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple


def build_document_stats(
    documents: Iterable[Dict[str, Any]],
    file_count: int | None = None,
    chunk_count: int | None = None,
) -> Dict[str, Any]:
    """Build document metrics and chart data."""

    docs = list(documents)
    derived_file_count = file_count if file_count is not None else len(docs)

    chart_data: List[Dict[str, Any]] = []
    derived_chunk_total = 0
    for doc in docs:
        title = doc.get("title") or doc.get("id") or "Document"
        chunk_total = (doc.get("metadata") or {}).get("chunk_count") or 0
        derived_chunk_total += chunk_total
        chart_data.append({"title": title, "chunk_count": chunk_total})

    derived_chunk_count = chunk_count if chunk_count is not None else derived_chunk_total

    return {
        "file_count": derived_file_count,
        "chunk_count": derived_chunk_count,
        "chart_data": chart_data,
    }


def build_history_stats(messages: Iterable[Dict[str, Any]]) -> Dict[str, int]:
    """Return counts for session history metrics."""

    total = 0
    user_count = 0
    assistant_count = 0
    for message in messages:
        total += 1
        role = message.get("role")
        if role == "user":
            user_count += 1
        elif role == "assistant":
            assistant_count += 1

    return {
        "total": total,
        "user": user_count,
        "assistant": assistant_count,
    }
