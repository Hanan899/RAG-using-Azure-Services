"""Shared UI helpers for consistent styling and navigation."""

from __future__ import annotations

import streamlit as st


def inject_global_styles() -> None:
    """Inject the global CSS styles for the app."""

    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700&family=Space+Grotesk:wght@600;700&display=swap');
        :root {
            --bg: #f6f7fb;
            --surface: #ffffff;
            --card: #ffffff;
            --text: #0f172a;
            --muted: #6b7280;
            --accent: #2563eb;
            --accent-dark: #1e40af;
            --border: #e2e8f0;
            --radius-lg: 18px;
            --radius-md: 12px;
            --shadow-soft: 0 8px 24px rgba(15, 23, 42, 0.08);
        }
        html, body, [class*="stApp"] { font-family: 'Manrope', sans-serif; color: var(--text); }
        .stApp {
            background: radial-gradient(circle at top left, #eef2ff 0%, #f8fafc 40%, #f6f7fb 100%);
        }
        [data-testid="stSidebarNav"] { display: none; }
        section[data-testid="stSidebar"] {
            background: #f8fafc;
            border-right: 1px solid var(--border);
        }
        .sidebar-spacer { height: 0.75rem; }
        h1, h2, h3, h4 { font-family: 'Space Grotesk', sans-serif; }
        .main .block-container { padding-top: 2.5rem; }
        .chat-container { max-width: 960px; margin: 0 auto; }
        .hero-card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: var(--radius-lg);
            padding: 1.25rem 1.5rem;
            box-shadow: var(--shadow-soft);
            margin-bottom: 1.5rem;
        }
        .sticky-page-header {
            position: sticky;
            top: 0.5rem;
            z-index: 30;
            background: radial-gradient(circle at top left, #eef2ff 0%, #f8fafc 40%, #f6f7fb 100%);
            padding: 0 0 0.35rem 0;
            margin-bottom: 1rem;
        }
        .sticky-page-header .hero-card {
            margin-bottom: 0;
        }
        .message-row { display: flex; margin: 0.5rem 0; }
        .message-row.user { justify-content: flex-end; }
        .message-row.assistant { justify-content: flex-start; }
        .message-bubble {
            max-width: 80%;
            padding: 1rem 1.25rem;
            border-radius: var(--radius-lg);
            font-size: 0.98rem;
            line-height: 1.6;
            white-space: normal;
            word-break: break-word;
            box-shadow: var(--shadow-soft);
        }
        .message-bubble.user {
            background: linear-gradient(135deg, var(--accent), #3b82f6);
            color: #fff;
            border: 1px solid rgba(255,255,255,0.15);
        }
        .message-bubble.assistant {
            background: var(--surface);
            color: var(--text);
            border: 1px solid var(--border);
        }
        .message-header { display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem; }
        .role-badge { display: inline-flex; align-items: center; justify-content: center; width: 24px; height: 24px; border-radius: 50%; font-size: 0.7rem; }
        .role-badge.user { background: rgba(255,255,255,0.2); color: #fff; }
        .role-badge.assistant { background: #e2e8f0; color: #334155; }
        .role-label { font-weight: 600; font-size: 0.85rem; }
        .message-content { white-space: normal; word-break: break-word; overflow-wrap: anywhere; }
        .message-content p { margin: 0 0 0.5rem 0; }
        .message-content p:last-child { margin-bottom: 0; }
        .message-content p:empty { display: none; margin: 0; }
        .message-content ul, .message-content ol { margin: 0.3rem 0 0.5rem 1.1rem; }
        .message-content li p { margin: 0; display: inline; }
        .message-content br + br { display: none; }
        .message-content pre { background: #0f172a; color: #f8fafc; padding: 0.75rem; border-radius: 10px; overflow-x: auto; }
        .sources-wrap { margin: 0.75rem 0 1.5rem 0; padding-left: 0.25rem; }
        .source-card {
            border-left: 3px solid var(--accent);
            padding: 0.75rem 0.75rem 0.75rem 0.9rem;
            margin-bottom: 0.75rem;
            background: var(--surface);
            border-radius: 12px;
            box-shadow: var(--shadow-soft);
        }
        .source-title { font-weight: 600; }
        .source-score { font-size: 0.8rem; color: var(--muted); }
        .source-content { font-size: 0.9rem; color: #334155; }
        .stButton > button { width: 100%; border-radius: 10px; }
        .stTextInput input { height: 44px; }
        .stButton > button { height: 44px; }
        button[kind="primary"] {
            background: var(--accent) !important;
            border: 1px solid var(--accent-dark) !important;
        }
        button[kind="primary"]:hover { filter: brightness(0.95); }
        .doc-title {
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        .doc-meta { font-size: 0.8rem; color: var(--muted); }
        .sidebar-section-title {
            font-weight: 700;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            font-size: 0.75rem;
            color: #64748b;
            margin-bottom: 0.5rem;
        }
        .sidebar-card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            padding: 0.75rem 0.9rem;
            box-shadow: var(--shadow-soft);
            margin-bottom: 1rem;
        }
        .brand {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            padding: 0.5rem 0;
            margin-bottom: 0.75rem;
        }
        .brand-logo {
            width: 38px;
            height: 38px;
            border-radius: 12px;
            background: linear-gradient(135deg, var(--accent), #3b82f6);
            color: #fff;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            font-size: 0.9rem;
            box-shadow: var(--shadow-soft);
        }
        .brand-title { font-weight: 700; font-size: 1rem; }
        .brand-subtitle { font-size: 0.8rem; color: var(--muted); }
        div[data-testid="stFileUploader"] {
            background: #ffffff;
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            padding: 0.5rem;
            box-shadow: var(--shadow-soft);
        }
        div[data-testid="stChatInput"] textarea {
            border-radius: 14px;
            border: 1px solid var(--border);
            background: #fff;
            box-shadow: var(--shadow-soft);
            min-height: 48px;
            line-height: 1.4;
        }
        .message-content table {
            width: 100%;
            border-collapse: collapse;
            margin: 0.75rem 0;
            font-size: 0.92rem;
        }
        .message-content th, .message-content td {
            border: 1px solid var(--border);
            padding: 0.6rem 0.7rem;
            text-align: left;
        }
        .message-content thead {
            background: #f1f5f9;
            font-weight: 600;
        }
        .message-content h1, .message-content h2, .message-content h3, .message-content h4 {
            margin: 0.35rem 0 0.2rem 0 !important;
            line-height: 1.3;
        }
        .message-content p + h1,
        .message-content p + h2,
        .message-content p + h3,
        .message-content p + h4,
        .message-content ul + h1,
        .message-content ul + h2,
        .message-content ul + h3,
        .message-content ul + h4,
        .message-content ol + h1,
        .message-content ol + h2,
        .message-content ol + h3,
        .message-content ol + h4 {
            margin-top: 0.5rem !important;
        }
        .message-content ul {
            margin: 0.3rem 0 0.5rem 1.1rem;
        }
        .message-content li {
            margin: 0.15rem 0;
        }
        @media (max-width: 768px) { .message-bubble { max-width: 95%; } }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_page_header(title: str, subtitle: str) -> None:
    """Render a sticky page header card shared across pages."""

    st.markdown(
        f"""
        <div class="sticky-page-header">
            <div class="hero-card">
                <h1>{title}</h1>
                <p>{subtitle}</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar_nav(current: str) -> None:
    """Render the branded sidebar navigation."""

    st.sidebar.markdown(
        """
        <div class="brand">
            <div class="brand-logo">RC</div>
            <div class="brand-text">
                <div class="brand-title">RAG Console</div>
                <div class="brand-subtitle">Enterprise Search</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.sidebar.markdown(
        "<div class='sidebar-section-title'>Navigation</div>", unsafe_allow_html=True
    )

    pages = [
        ("Chat", "app.py"),
        ("Documents", "pages/documents.py"),
        ("Session History", "pages/session_history.py"),
        ("Settings", "pages/settings.py"),
    ]

    if hasattr(st.sidebar, "page_link"):
        for label, path in pages:
            st.sidebar.page_link(path, label=label)
    else:
        labels = [label for label, _ in pages]
        index = labels.index(current) if current in labels else 0
        selection = st.sidebar.radio("", labels, index=index, label_visibility="collapsed")
        if selection != current and hasattr(st, "switch_page"):
            path_map = {label: path for label, path in pages}
            st.switch_page(path_map[selection])

    st.sidebar.markdown("<div class='sidebar-spacer'></div>", unsafe_allow_html=True)
