"""Unit tests for chat component markdown rendering."""

from __future__ import annotations

from frontend.components.chat_component import _format_message_html


def test_markdown_bold_rendering() -> None:
    """Ensure markdown bold renders to strong tag."""

    html = _format_message_html({"role": "assistant", "content": "**bold**"})
    assert "<strong>bold</strong>" in html


def test_markdown_sanitization_strips_script() -> None:
    """Ensure unsafe script tags are removed."""

    html = _format_message_html(
        {"role": "assistant", "content": "<script>alert('x')</script>safe"}
    )
    assert "<script>" not in html
    assert "safe" in html


def test_message_wrapper_classes() -> None:
    """Ensure role classes appear in rendered HTML."""

    html = _format_message_html({"role": "user", "content": "hi"})
    assert "message-row user" in html
    assert "message-bubble user" in html


def test_markdown_table_rendering_preserved() -> None:
    """Ensure markdown tables render into HTML table tags."""

    markdown_table = "| A | B |\n| --- | --- |\n| 1 | 2 |"
    html = _format_message_html({"role": "assistant", "content": markdown_table})
    assert "<table>" in html
    assert "<thead>" in html
    assert "<td>2</td>" in html


def test_extra_blank_lines_are_compacted() -> None:
    """Multiple blank lines should not create oversized gaps in rendered output."""

    content = "**Answer**\n\n\u200b\n\n### Overview\n\n\nLine"
    html = _format_message_html({"role": "assistant", "content": content})
    assert "<h3>Overview</h3>" in html
    assert "<p><strong>Answer</strong></p>" in html
    assert "<p></p>" not in html


def test_nbsp_only_lines_do_not_create_gaps() -> None:
    """Non-breaking-space lines should be treated as blank and compacted."""

    content = "**Answer**\n\n\u00a0\n\n### Scope\n\nText"
    html = _format_message_html({"role": "assistant", "content": content})
    assert "<h3>Scope</h3>" in html
    assert "&nbsp;" not in html
