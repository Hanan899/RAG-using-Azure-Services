"""Pydantic schemas for requests and responses."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """Single chat message used for conversation history."""

    role: str = Field(..., description="Role such as 'user' or 'assistant'.")
    content: str = Field(..., description="Message content.")


class ChatRequest(BaseModel):
    """Request payload for the chat endpoint."""

    message: str = Field(..., description="User's prompt.")
    history: Optional[List[ChatMessage]] = Field(
        default=None, description="Optional prior conversation messages."
    )
    top_k: Optional[int] = Field(
        default=5, description="Number of search results to retrieve."
    )
    temperature: Optional[float] = Field(
        default=0.2, description="Sampling temperature for generation."
    )
    max_tokens: Optional[int] = Field(
        default=512, description="Maximum tokens for generation."
    )


class Source(BaseModel):
    """Source document excerpt returned alongside answers."""

    title: Optional[str] = Field(default=None, description="Source title or identifier.")
    content: str = Field(..., description="Retrieved content snippet.")
    score: Optional[float] = Field(default=None, description="Search relevance score.")
    metadata: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional metadata for the source."
    )


class SourceDocument(BaseModel):
    """Structured source document with attribution details."""

    id: str = Field(..., description="Document identifier.")
    title: str = Field(..., description="Document title.")
    relevance_score: float = Field(..., description="Relevance score from search.")
    excerpt: str = Field(..., description="Relevant excerpt from the document.")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata for the source."
    )


class ChatResponse(BaseModel):
    """Response payload for the chat endpoint."""

    answer: str = Field(..., description="Assistant response.")
    sources: List[SourceDocument] = Field(
        default_factory=list, description="Cited sources."
    )
    has_sufficient_context: bool = Field(
        default=True, description="Whether sufficient context was found."
    )
    tokens_used: int = Field(default=0, description="Total tokens consumed.")
    suggested_actions: Optional[List[str]] = Field(
        default=None, description="Suggested actions when context is insufficient."
    )
