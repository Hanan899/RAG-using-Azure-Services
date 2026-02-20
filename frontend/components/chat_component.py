"""Chat rendering helpers with custom styling and safe markdown."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

import streamlit as st
import markdown
import bleach

ALLOWED_TAGS = [
    "p",
    "br",
    "strong",
    "em",
    "ul",
    "ol",
    "li",
    "code",
    "pre",
    "blockquote",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "a",
    "table",
    "thead",
    "tbody",
    "tr",
    "th",
    "td",
]
ALLOWED_ATTRIBUTES = {"a": ["href", "title", "target", "rel"]}


def _compact_blank_lines(text: str) -> str:
    """Collapse whitespace-only line runs to a single blank line."""

    if not text:
        return ""

    compacted: List[str] = []
    blank_open = False
    for raw_line in text.split("\n"):
        line = raw_line.replace("\u200b", "").replace("\ufeff", "").replace("\u00a0", " ")
        if not line.strip():
            if not blank_open:
                compacted.append("")
                blank_open = True
            continue

        compacted.append(line.rstrip())
        blank_open = False

    return "\n".join(compacted).strip()


def _render_markdown(content: str) -> str:
    """Render markdown to sanitized HTML."""

    normalized_content = (content or "").replace("\r\n", "\n").replace("\r", "\n")
    normalized_content = _compact_blank_lines(normalized_content)

    html_content = markdown.markdown(
        normalized_content,
        extensions=["extra", "sane_lists"],
        output_format="html5",
    )
    cleaned_html = bleach.clean(
        html_content,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        strip=True,
    )
    cleaned_html = re.sub(
        r"<p>(?:\s|&nbsp;|&#160;|<br\s*/?>)*</p>",
        "",
        cleaned_html,
        flags=re.IGNORECASE,
    )
    cleaned_html = re.sub(r"(?:<br\s*/?>\s*){2,}", "<br>", cleaned_html, flags=re.IGNORECASE)
    return cleaned_html.strip()


def _format_message_html(message: Dict[str, Any]) -> str:
    """Return HTML for a single chat message."""

    role = message.get("role", "assistant")
    content = _render_markdown(message.get("content", ""))
    label = "User" if role == "user" else "Assistant"
    badge = "U" if role == "user" else "AI"

    return (
        f"<div class='message-row {role}'>"
        f"  <div class='message-bubble {role}'>"
        f"    <div class='message-header'>"
        f"      <span class='role-badge {role}'>{badge}</span>"
        f"      <span class='role-label'>{label}</span>"
        f"    </div>"
        f"    <div class='message-content'>{content}</div>"
        f"  </div>"
        f"</div>"
    )


def render_message(message: Dict[str, Any], container: Optional[Any] = None) -> None:
    """Render a single chat message."""

    target = container or st
    target.markdown(_format_message_html(message), unsafe_allow_html=True)


def render_sources(sources: List[Dict[str, Any]], container: Optional[Any] = None) -> None:
    """Render source citations for an assistant message."""

    if not sources:
        return

    target = container or st
    items = []
    for source in sources:
        title = source.get("title") or source.get("id") or "Source"
        score = source.get("score")
        snippet = _render_markdown(source.get("excerpt") or source.get("content", ""))
        score_text = f"Score: {score:.2f}" if isinstance(score, (int, float)) else ""
        items.append(
            "<div class='source-card'>"
            f"<div class='source-title'>{title}</div>"
            f"<div class='source-score'>{score_text}</div>"
            f"<div class='source-content'>{snippet}</div>"
            "</div>"
        )

    target.markdown(
        "<div class='sources-wrap'>" + "".join(items) + "</div>",
        unsafe_allow_html=True,
    )


def render_chat_history(messages: List[Dict[str, Any]]) -> None:
    """Render the full conversation history without inline source cards."""

    for message in messages:
        render_message(message)
