"""Azure OpenAI chat completion + embedding service with retry and token counting."""

from __future__ import annotations

from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

import tiktoken
from openai import APIError, APITimeoutError, AsyncAzureOpenAI, RateLimitError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from app.config.config import settings
from app.utils.prompt_templates import SYSTEM_PROMPT
from app.utils.logging import get_logger

logger = get_logger(__name__)


class AzureOpenAIService:
    """Service for Azure OpenAI chat and embedding-related utilities."""

    def __init__(self) -> None:
        # Instantiate the Azure OpenAI client once for reuse.
        self._client = AsyncAzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
        )
        self._encoding = tiktoken.get_encoding("cl100k_base")

    @retry(
        retry=retry_if_exception_type((RateLimitError, APIError, APITimeoutError)),
        wait=wait_exponential_jitter(initial=1, max=30),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    async def generate_embedding(self, text: str) -> List[float]:
        """Generate an embedding vector for a single text input."""

        if not text:
            return []

        try:
            response = await self._client.embeddings.create(
                model=settings.azure_openai_embedding_deployment_name,
                input=text,
            )
            if not response.data:
                return []
            vector = response.data[0].embedding or []
            self._warn_on_dimension_mismatch(vector)
            return vector
        except Exception:
            logger.exception("Embedding generation failed")
            raise

    @retry(
        retry=retry_if_exception_type((RateLimitError, APIError, APITimeoutError)),
        wait=wait_exponential_jitter(initial=1, max=30),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    async def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a batch of texts efficiently."""

        if not texts:
            return []

        try:
            response = await self._client.embeddings.create(
                model=settings.azure_openai_embedding_deployment_name,
                input=texts,
            )
            vectors: List[Optional[List[float]]] = [None] * len(texts)
            for item in response.data:
                if item.index is not None and 0 <= item.index < len(vectors):
                    vectors[item.index] = item.embedding or []

            normalized: List[List[float]] = []
            for vector in vectors:
                safe_vector = vector or []
                self._warn_on_dimension_mismatch(safe_vector)
                normalized.append(safe_vector)

            return normalized
        except Exception:
            logger.exception("Batch embedding generation failed")
            raise

    @retry(
        retry=retry_if_exception_type((RateLimitError, APIError, APITimeoutError)),
        wait=wait_exponential_jitter(initial=1, max=30),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    async def chat_completion(
        self,
        query: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        context_documents: Optional[List[Dict[str, Any]]] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 512,
    ) -> Tuple[str, int]:
        """Generate a chat completion response with context."""

        messages = self._build_messages(
            query, conversation_history, context_documents, system_prompt
        )
        prompt_tokens = self._count_tokens(messages)

        response = await self._client.chat.completions.create(
            model=settings.azure_openai_deployment_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        answer = ""
        if response.choices:
            answer = response.choices[0].message.content or ""

        usage_tokens = response.usage.total_tokens if response.usage else 0
        if usage_tokens == 0:
            completion_tokens = self._count_text_tokens(answer)
            usage_tokens = prompt_tokens + completion_tokens

        return answer, usage_tokens

    @retry(
        retry=retry_if_exception_type((RateLimitError, APIError, APITimeoutError)),
        wait=wait_exponential_jitter(initial=1, max=30),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    async def chat_completion_stream(
        self,
        query: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        context_documents: Optional[List[Dict[str, Any]]] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 512,
    ) -> AsyncGenerator[str, None]:
        """Stream chat completion response chunks for real-time updates."""

        messages = self._build_messages(
            query, conversation_history, context_documents, system_prompt
        )

        stream = await self._client.chat.completions.create(
            model=settings.azure_openai_deployment_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )

        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield delta.content

    def _build_messages(
        self,
        query: str,
        conversation_history: Optional[List[Dict[str, str]]],
        context_documents: Optional[List[Dict[str, Any]]],
        system_prompt: Optional[str],
    ) -> List[Dict[str, str]]:
        """Construct the chat prompt with optional context and history."""

        prompt = system_prompt or SYSTEM_PROMPT
        messages: List[Dict[str, str]] = [{"role": "system", "content": prompt}]

        if context_documents:
            context_text = self._format_context(context_documents)
            messages.append({"role": "system", "content": context_text})

        for message in conversation_history or []:
            messages.append({"role": message["role"], "content": message["content"]})

        if query:
            messages.append({"role": "user", "content": query})
        return messages

    def _format_context(self, documents: List[Dict[str, Any]]) -> str:
        """Format context documents into a prompt segment."""

        lines = ["Context:"]
        for idx, doc in enumerate(documents, start=1):
            title = doc.get("title") or doc.get("id") or f"Doc {idx}"
            content = doc.get("content", "")
            lines.append(f"[{idx}] {title}\n{content}")
        return "\n\n".join(lines)

    def _count_tokens(self, messages: List[Dict[str, str]]) -> int:
        """Count tokens for a list of chat messages."""

        total = 0
        for message in messages:
            total += self._count_text_tokens(message.get("content", ""))
        return total

    def _count_text_tokens(self, text: str) -> int:
        """Estimate token count for a single text string."""

        if not text:
            return 0
        return len(self._encoding.encode(text))

    def _warn_on_dimension_mismatch(self, vector: List[float]) -> None:
        if not vector:
            return
        if len(vector) != settings.embedding_dimensions:
            logger.warning(
                "Embedding dimension mismatch: expected %s, got %s",
                settings.embedding_dimensions,
                len(vector),
            )
