"""Core RAG pipeline service combining search and OpenAI generation."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from app.config.config import settings
from app.models.schemas import ChatRequest, ChatResponse, SourceDocument
from app.services.openai_service import AzureOpenAIService
from app.services.search_service import AzureSearchService
from app.utils.logging import get_logger
from app.utils.prompt_templates import STRICT_RAG_SYSTEM_PROMPT

logger = get_logger(__name__)


class RAGService:
    """RAG pipeline that retrieves context and generates grounded answers."""

    def __init__(
        self,
        search_service: Optional[AzureSearchService] = None,
        openai_service: Optional[AzureOpenAIService] = None,
        relevance_threshold: Optional[float] = None,
        memory_limit: int = 5,
    ) -> None:
        # Allow dependency injection for testing or customization.
        self._search_service = search_service or AzureSearchService()
        self._openai_service = openai_service or AzureOpenAIService()
        self._relevance_threshold = (
            relevance_threshold
            if relevance_threshold is not None
            else settings.minimum_relevance_score
        )
        self._memory_limit = memory_limit

    async def process_query(
        self,
        query: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        top_k: int = 5,
        temperature: float = 0.2,
        max_tokens: int = 512,
        generate_answer: bool = True,
    ) -> Dict[str, Any]:
        """Run the end-to-end RAG pipeline and return answer + sources."""

        embedding = None
        try:
            embedding = await self._openai_service.generate_embedding(query)
            if not embedding:
                embedding = None
        except Exception:  # pragma: no cover - defensive fallback
            logger.exception("Embedding generation failed; falling back to text-only search.")

        raw_results = await self._search_service.hybrid_search(
            query_text=query,
            query_embedding=embedding,
            top_k=top_k,
        )

        filtered_results = self._filter_by_relevance(raw_results)
        reranked_results = self.rerank_results(filtered_results)

        if not reranked_results:
            return {
                "answer": (
                    "I don't have enough information in the knowledge base to answer this question. "
                    "Please upload relevant documents or rephrase your query."
                ),
                "sources": [],
                "tokens_used": 0,
                "has_sufficient_context": False,
                "suggested_actions": [
                    "Upload relevant documents",
                    "Try different keywords",
                    "Check available documents",
                ],
                "context_documents": [],
            }

        if not generate_answer:
            return {
                "answer": "",
                "sources": self.extract_sources(reranked_results),
                "tokens_used": 0,
                "has_sufficient_context": True,
                "suggested_actions": None,
                "context_documents": reranked_results,
            }

        context = self.format_context(reranked_results)
        strict_prompt = STRICT_RAG_SYSTEM_PROMPT.format(context=context, question=query)

        answer, tokens_used = await self._openai_service.chat_completion(
            query="",
            conversation_history=[],
            context_documents=None,
            system_prompt=strict_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        no_info_response = self._is_no_info_response(answer)
        sources = self.extract_sources(reranked_results)
        answer = self._normalize_answer(
            answer,
            sources=[] if no_info_response else sources,
        )

        if no_info_response:
            return {
                "answer": answer,
                "sources": [],
                "tokens_used": tokens_used,
                "has_sufficient_context": False,
                "suggested_actions": [
                    "Upload relevant documents",
                    "Try different keywords",
                    "Check available documents",
                ],
                "context_documents": [],
            }

        return {
            "answer": answer,
            "sources": sources,
            "tokens_used": tokens_used,
            "has_sufficient_context": True,
            "suggested_actions": None,
            "context_documents": reranked_results,
        }

    async def answer_question(self, request: ChatRequest) -> ChatResponse:
        """Compatibility wrapper for the existing API routes."""

        result = await self.process_query(
            query=request.message,
            top_k=request.top_k or 5,
            temperature=request.temperature or 0.2,
            max_tokens=request.max_tokens or 512,
        )

        sources = [
            SourceDocument(
                id=item.get("id") or "",
                title=item.get("title") or "",
                relevance_score=float(item.get("relevance_score") or 0),
                excerpt=item.get("excerpt", ""),
                metadata=item.get("metadata") or {},
            )
            for item in result["sources"]
        ]
        return ChatResponse(
            answer=result["answer"],
            sources=sources,
            has_sufficient_context=result.get("has_sufficient_context", True),
            tokens_used=result.get("tokens_used", 0),
            suggested_actions=result.get("suggested_actions"),
        )

    def format_context(self, documents: List[Dict[str, Any]]) -> str:
        """Convert search results into a context string for the prompt."""

        if not documents:
            return ""

        chunks: List[str] = []
        for idx, doc in enumerate(documents, start=1):
            title = doc.get("title") or doc.get("id") or f"Source {idx}"
            doc_id = doc.get("id") or f"doc-{idx}"
            metadata = doc.get("metadata") or {}
            metadata_text = json.dumps(metadata, ensure_ascii=False)
            content = doc.get("content", "")
            chunks.append(
                f"[{idx}] Document ID: {doc_id}\nTitle: {title}\nMetadata: {metadata_text}\n{content}"
            )
        return "\n\n".join(chunks)

    def extract_sources(self, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract source references for response citations."""

        sources: List[Dict[str, Any]] = []
        for doc in documents:
            sources.append(
                {
                    "id": doc.get("id"),
                    "title": doc.get("title") or doc.get("source"),
                    "relevance_score": float(doc.get("score") or 0),
                    "excerpt": self._build_excerpt(doc.get("content", "")),
                    "metadata": doc.get("metadata") or {},
                }
            )
        return sources

    def rerank_results(self, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Optional reranking step based on relevance scores."""

        return sorted(
            documents,
            key=lambda item: item.get("score", 0) or 0,
            reverse=True,
        )

    def _filter_by_relevance(self, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter out documents below the relevance threshold."""

        filtered = []
        for doc in documents:
            score = doc.get("score") or 0
            if score >= self._relevance_threshold:
                filtered.append(doc)
        return filtered

    def _build_excerpt(self, content: str) -> str:
        """Return a short excerpt for source attribution."""

        if not content:
            return ""
        return content[:300]

    def _normalize_answer(
        self,
        answer: str,
        sources: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Remove inline citations, normalize formatting, and append sources."""

        if not answer:
            return answer

        cleaned = answer.replace("\r\n", "\n").replace("\r", "\n")
        cleaned = cleaned.replace("\u200b", "").replace("\ufeff", "")
        cleaned = re.sub(r"\[Source:.*?\]", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(
            r"\n*\**\s*Sources\s*:.*$",
            "",
            cleaned,
            flags=re.IGNORECASE | re.DOTALL,
        )
        cleaned = re.sub(r"^---\s*$", "", cleaned, flags=re.MULTILINE)
        cleaned = self._repair_malformed_prefix(cleaned)
        cleaned = self._normalize_markdown_structure(cleaned)
        cleaned = self._format_bullets_if_needed(cleaned)
        cleaned = self._compact_blank_lines(cleaned)

        if not cleaned.startswith("**Answer**"):
            cleaned = f"**Answer**\n\n{cleaned}".strip()

        cleaned = self._compact_blank_lines(cleaned)

        if not sources:
            return cleaned

        footer = self._build_sources_footer(sources)
        if footer:
            cleaned = f"{cleaned}\n\n{footer}"
        return cleaned

    def _format_bullets_if_needed(self, text: str) -> str:
        """Convert inline dash lists into proper bullet lists."""

        if "\n" in text or " - " not in text:
            return text

        parts = [part.strip() for part in text.split(" - ") if part.strip()]
        if len(parts) < 3:
            return text

        lines = [f"- {part}" for part in parts]
        return "\n".join(lines)

    @staticmethod
    def _repair_malformed_prefix(text: str) -> str:
        """Fix malformed answer prefixes like '|AnswerText' from model output."""

        cleaned = text.lstrip("|` \n")
        cleaned = re.sub(
            r"^(?:\*{0,2}\s*)?answer(?:\*{0,2})\s*[:\-]?\s*",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(r"^(?:answer)(?=[A-Z])", "", cleaned, flags=re.IGNORECASE)
        return cleaned.strip()

    @staticmethod
    def _normalize_markdown_structure(text: str) -> str:
        """Improve markdown readability by fixing missing line breaks."""

        normalized = re.sub(r"(:)\s*(#{2,6}\s)", r"\1\n\n\2", text)
        normalized = re.sub(r"(?<!\n)(#{2,6}\s)", r"\n\n\1", normalized)
        normalized = re.sub(r"([.!?])\s*-\s+", r"\1\n- ", normalized)
        normalized = re.sub(r"(#{2,6}[^\n]*)\s*-\s+", r"\1\n- ", normalized)
        normalized = re.sub(r"[ \t]+\n", "\n", normalized)
        normalized = re.sub(r"\n{3,}", "\n\n", normalized)
        return normalized.strip()

    @staticmethod
    def _compact_blank_lines(text: str, max_blank_lines: int = 1) -> str:
        """Collapse whitespace-only runs to a compact, readable markdown layout."""

        if not text:
            return text

        text = text.replace("\u200b", "").replace("\ufeff", "")
        compacted: List[str] = []
        blank_count = 0
        for raw_line in text.split("\n"):
            line = (
                raw_line.replace("\u200b", "")
                .replace("\ufeff", "")
                .replace("\u00a0", " ")
                .rstrip()
            )
            if not line.strip():
                blank_count += 1
                if blank_count <= max_blank_lines:
                    compacted.append("")
                continue

            blank_count = 0
            compacted.append(line)

        return "\n".join(compacted).strip()

    @staticmethod
    def _is_no_info_response(answer: str) -> bool:
        """Detect model responses that indicate missing context information."""

        if not answer:
            return True

        text = answer.lower()
        markers = [
            "i cannot find this information in the available documents",
            "i don't have enough information in the knowledge base",
            "not available in the provided context",
        ]
        return any(marker in text for marker in markers)

    def _build_sources_footer(self, sources: List[Dict[str, Any]]) -> str:
        """Build a single sources footer from the source list."""

        if not sources:
            return ""

        grouped: Dict[str, Dict[str, Any]] = {}
        for source in sources:
            title = str(source.get("title") or source.get("id") or "Document")
            metadata = source.get("metadata") or {}
            page_number = self._coerce_int(metadata.get("page_number"))
            chunk_index = self._coerce_int(metadata.get("chunk_index"))
            section_label = self._extract_section_label(
                metadata,
                str(source.get("excerpt") or ""),
            )

            if title not in grouped:
                grouped[title] = {
                    "pages": set(),
                    "chunks": set(),
                    "sections": set(),
                    "plain": False,
                }

            if page_number is not None:
                grouped[title]["pages"].add(page_number)
            elif chunk_index is not None:
                grouped[title]["chunks"].add(chunk_index + 1)
            else:
                grouped[title]["plain"] = True

            if section_label:
                grouped[title]["sections"].add(section_label)

        entries = []
        for title in sorted(grouped, key=lambda item: item.lower()):
            source_group = grouped[title]
            pages = sorted(source_group["pages"])
            chunks = sorted(source_group["chunks"])
            sections = sorted(source_group["sections"], key=lambda item: item.lower())

            label_parts: List[str] = []
            if sections:
                section_text = (
                    f"Section: {sections[0]}"
                    if len(sections) == 1
                    else "Sections: " + ", ".join(sections)
                )
                label_parts.append(section_text)
            if pages:
                page_text = (
                    f"Page {pages[0]}"
                    if len(pages) == 1
                    else "Pages " + ", ".join(str(page) for page in pages)
                )
                label_parts.append(page_text)
            elif chunks and not sections:
                chunk_text = (
                    f"Chunk {chunks[0]}"
                    if len(chunks) == 1
                    else "Chunks " + ", ".join(str(chunk) for chunk in chunks)
                )
                label_parts.append(chunk_text)

            if label_parts:
                entries.append(f"[Source: {title} ({', '.join(label_parts)})]")
            else:
                entries.append(f"[Source: {title}]")

        return "Sources: " + " ".join(entries)

    @staticmethod
    def _coerce_int(value: Any) -> Optional[int]:
        """Coerce page/chunk metadata values to integers safely."""

        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _extract_section_label(
        metadata: Dict[str, Any],
        excerpt: str = "",
    ) -> Optional[str]:
        """Extract a user-friendly section name from metadata or source excerpt."""

        section_keys = (
            "section",
            "section_name",
            "relevant_section",
            "heading",
            "subheading",
        )
        for key in section_keys:
            value = metadata.get(key)
            if value is None:
                continue
            label = str(value).strip()
            if label:
                return label
        return RAGService._infer_section_from_text(excerpt)

    @staticmethod
    def _infer_section_from_text(text: str) -> Optional[str]:
        """Infer a section-like label from source text when metadata is missing."""

        if not text:
            return None

        normalized = " ".join(
            text.replace("\u200b", "")
            .replace("\ufeff", "")
            .replace("\u00a0", " ")
            .split()
        ).strip()
        if not normalized:
            return None

        patterns = [
            r"(?i)\b(part\s+\d+[a-z]?\s*:\s*[A-Za-z][A-Za-z0-9 ,&()/\'\-]{3,90})",
            r"(?i)\b(section\s+\d+[a-z]?\s*:\s*[A-Za-z][A-Za-z0-9 ,&()/\'\-]{3,90})",
            r"\b(\d+(?:\.\d+)*[\.)]?\s+[A-Z][A-Za-z0-9&()/\'\-]*(?:\s+[A-Za-z][A-Za-z0-9&()/\'\-]*){0,8})",
        ]

        for pattern in patterns:
            match = re.search(pattern, normalized)
            if not match:
                continue
            label = match.group(1).strip().rstrip(".,;:-")
            if 3 <= len(label) <= 110:
                return label
        return None


# Backwards-compatible alias for older import paths.
RagService = RAGService
