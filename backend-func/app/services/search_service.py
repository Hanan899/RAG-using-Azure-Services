"""Async Azure AI Search service with vector and hybrid search support."""

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Optional

from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import HttpResponseError, ServiceRequestError
from azure.search.documents.aio import SearchClient
from azure.search.documents.indexes.aio import SearchIndexClient
from azure.search.documents.indexes.models import (
    HnswAlgorithmConfiguration,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SearchableField,
    SemanticConfiguration,
    SemanticField,
    SemanticPrioritizedFields,
    SemanticSearch,
    SimpleField,
    VectorSearch,
    VectorSearchProfile,
)
from azure.search.documents.models import VectorizedQuery

from app.config.config import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


class IndexConfigurationError(RuntimeError):
    """Raised when the index schema cannot be updated due to incompatible changes."""


class SearchServiceUnavailableError(RuntimeError):
    """Raised when Azure Search cannot be reached due to connectivity issues."""


class AzureSearchService:
    """Service for managing and querying Azure AI Search indexes."""

    def __init__(self) -> None:
        # Initialize clients for index management and document search.
        credential = AzureKeyCredential(settings.azure_search_admin_key)
        self._index_name = settings.azure_search_index_name
        self._search_client = SearchClient(
            endpoint=settings.azure_search_service_endpoint,
            index_name=self._index_name,
            credential=credential,
        )
        self._index_client = SearchIndexClient(
            endpoint=settings.azure_search_service_endpoint,
            credential=credential,
        )
        self._use_semantic = settings.azure_search_use_semantic
        self._auto_create_index = settings.azure_search_auto_create_index
        self._embedding_dimensions = settings.embedding_dimensions
        self._index_ready = False
        self._index_lock = asyncio.Lock()
        logger.info("AzureSearchService initialized for index '%s'", self._index_name)

    async def create_or_update_index(self) -> None:
        """Create or update the search index with vector and semantic settings."""

        try:
            index = self._build_index_schema()
            await self._index_client.create_or_update_index(index)
            logger.info("Index '%s' created or updated", self._index_name)
        except ServiceRequestError as exc:
            raise SearchServiceUnavailableError(
                "Cannot reach Azure Search. Verify endpoint, firewall/network rules, and service availability."
            ) from exc
        except HttpResponseError as exc:
            message = str(exc)
            if "CannotChangeExistingField" in message or "cannot be changed" in message:
                raise IndexConfigurationError(
                    "Embedding dimensions changed. Set a new AZURE_SEARCH_INDEX_NAME or delete/recreate the existing index."
                ) from exc
            logger.exception("Failed to create or update index '%s'", self._index_name)
            raise
        except Exception:
            logger.exception("Failed to create or update index '%s'", self._index_name)
            raise

    async def upload_documents(self, documents: List[Dict[str, Any]]) -> None:
        """Upload a batch of documents to the search index."""

        if not documents:
            logger.info("No documents provided for upload")
            return

        await self._ensure_index()

        normalized = [self._normalize_document(doc) for doc in documents]

        try:
            results = await self._search_client.upload_documents(documents=normalized)
            failed = [result for result in results if not result.succeeded]
            if failed:
                raise RuntimeError(f"Failed to upload {len(failed)} documents")
            logger.info("Uploaded %s documents", len(normalized))
        except ServiceRequestError as exc:
            raise SearchServiceUnavailableError(
                "Cannot reach Azure Search. Verify endpoint, firewall/network rules, and service availability."
            ) from exc
        except Exception:
            logger.exception("Document upload failed")
            raise

    async def search_documents(
        self, query_embedding: List[float], top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """Perform vector similarity search using the query embedding."""

        await self._ensure_index()

        try:
            vector_query = VectorizedQuery(
                vector=query_embedding,
                k_nearest_neighbors=top_k,
                fields="embedding",
            )
            results = await self._search_client.search(
                search_text="*",
                vector_queries=[vector_query],
                top=top_k,
            )
            normalized = await self._collect_results(results)
            logger.info("Vector search returned %s results", len(normalized))
            return normalized
        except ServiceRequestError as exc:
            raise SearchServiceUnavailableError(
                "Cannot reach Azure Search. Verify endpoint, firewall/network rules, and service availability."
            ) from exc
        except Exception:
            logger.exception("Vector search failed")
            raise

    async def hybrid_search(
        self,
        query_text: str,
        query_embedding: Optional[List[float]],
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Combine keyword and vector search with semantic fallback."""

        await self._ensure_index()

        vector_queries = None
        if query_embedding:
            vector_queries = [
                VectorizedQuery(
                    vector=query_embedding,
                    k_nearest_neighbors=top_k,
                    fields="embedding",
                )
            ]

        try:
            search_text = query_text or "*"
            if self._use_semantic:
                results = await self._search_client.search(
                    search_text=search_text,
                    vector_queries=vector_queries,
                    top=top_k,
                    query_type="semantic",
                    semantic_configuration_name="semantic-config",
                )
            else:
                results = await self._search_client.search(
                    search_text=search_text,
                    vector_queries=vector_queries,
                    top=top_k,
                )
            normalized = await self._collect_results(results)
            logger.info("Hybrid search returned %s results", len(normalized))
            return normalized
        except ServiceRequestError as exc:
            raise SearchServiceUnavailableError(
                "Cannot reach Azure Search. Verify endpoint, firewall/network rules, and service availability."
            ) from exc
        except HttpResponseError:
            logger.exception("Semantic search failed; falling back to keyword search")
            try:
                results = await self._search_client.search(
                    search_text=search_text,
                    vector_queries=vector_queries,
                    top=top_k,
                )
                normalized = await self._collect_results(results)
                logger.info("Keyword fallback returned %s results", len(normalized))
                return normalized
            except ServiceRequestError as exc:
                raise SearchServiceUnavailableError(
                    "Cannot reach Azure Search. Verify endpoint, firewall/network rules, and service availability."
                ) from exc
        except Exception:
            logger.exception("Hybrid search failed")
            raise

    async def delete_documents(self, document_ids: List[str]) -> None:
        """Delete documents by ID from the index."""

        if not document_ids:
            logger.info("No document IDs provided for deletion")
            return

        await self._ensure_index()

        try:
            documents = [{"id": doc_id} for doc_id in document_ids]
            results = await self._search_client.delete_documents(documents=documents)
            failed = [result for result in results if not result.succeeded]
            if failed:
                raise RuntimeError(f"Failed to delete {len(failed)} documents")
            logger.info("Deleted %s documents", len(document_ids))
        except ServiceRequestError as exc:
            raise SearchServiceUnavailableError(
                "Cannot reach Azure Search. Verify endpoint, firewall/network rules, and service availability."
            ) from exc
        except Exception:
            logger.exception("Document deletion failed")
            raise

    async def list_all_documents(self, batch_size: int = 1000) -> List[Dict[str, Any]]:
        """List all indexed documents in pages (avoids the default top=50 cap)."""

        await self._ensure_index()

        collected: List[Dict[str, Any]] = []
        skip = 0
        page_size = max(1, min(batch_size, 1000))

        try:
            while True:
                results = await self._search_client.search(
                    search_text="*",
                    top=page_size,
                    skip=skip,
                )
                page = await self._collect_results(results)
                if not page:
                    break
                collected.extend(page)
                if len(page) < page_size:
                    break
                skip += len(page)

            logger.info("List-all search returned %s results", len(collected))
            return collected
        except ServiceRequestError as exc:
            raise SearchServiceUnavailableError(
                "Cannot reach Azure Search. Verify endpoint, firewall/network rules, and service availability."
            ) from exc
        except Exception:
            logger.exception("List-all search failed")
            raise

    async def get_index_stats(self) -> Dict[str, Any]:
        """Fetch index statistics such as document count."""

        try:
            stats = await self._index_client.get_index_statistics(self._index_name)
            if isinstance(stats, dict):
                count = stats.get("document_count") or stats.get("documentCount")
            else:
                count = getattr(stats, "document_count", None)
            return {"document_count": count or 0}
        except ServiceRequestError:
            logger.warning(
                "Cannot reach Azure Search while fetching index statistics; using fallback stats."
            )
            return {}
        except Exception:
            logger.exception("Failed to fetch index statistics")
            return {}

    async def close(self) -> None:
        """Close underlying Azure Search clients."""

        await self._search_client.close()
        await self._index_client.close()

    async def _ensure_index(self) -> None:
        """Create the index on first use when auto-provisioning is enabled."""

        if not self._auto_create_index or self._index_ready:
            return

        async with self._index_lock:
            if self._index_ready:
                return
            await self.create_or_update_index()
            self._index_ready = True

    def _build_index_schema(self) -> SearchIndex:
        """Build the index schema with vector and semantic configuration."""

        fields = [
            SimpleField(name="id", type=SearchFieldDataType.String, key=True),
            SearchableField(name="title", type=SearchFieldDataType.String),
            SearchableField(name="content", type=SearchFieldDataType.String),
            SearchableField(name="metadata", type=SearchFieldDataType.String),
            SearchField(
                name="embedding",
                type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                searchable=True,
                vector_search_dimensions=self._embedding_dimensions,
                vector_search_profile_name="vector-profile",
            ),
        ]

        vector_search = VectorSearch(
            algorithms=[HnswAlgorithmConfiguration(name="hnsw-config")],
            profiles=[
                VectorSearchProfile(
                    name="vector-profile",
                    algorithm_configuration_name="hnsw-config",
                )
            ],
        )

        semantic_config = SemanticConfiguration(
            name="semantic-config",
            prioritized_fields=SemanticPrioritizedFields(
                title_field=SemanticField(field_name="title"),
                content_fields=[SemanticField(field_name="content")],
                keywords_fields=[SemanticField(field_name="metadata")],
            ),
        )

        semantic_search = SemanticSearch(configurations=[semantic_config])

        return SearchIndex(
            name=self._index_name,
            fields=fields,
            vector_search=vector_search,
            semantic_search=semantic_search,
        )

    async def _collect_results(self, results) -> List[Dict[str, Any]]:
        """Normalize search results into a consistent dictionary format."""

        normalized: List[Dict[str, Any]] = []
        async for result in results:
            document = dict(result)
            content = (
                document.get("content")
                or document.get("chunk")
                or document.get("text")
                or ""
            )
            title = document.get("title") or document.get("source") or document.get("id")
            score = document.get("@search.score")

            raw_metadata = document.get("metadata")
            parsed_metadata: Dict[str, Any] = {}
            if isinstance(raw_metadata, str):
                try:
                    parsed_metadata = json.loads(raw_metadata)
                except json.JSONDecodeError:
                    parsed_metadata = {"raw_metadata": raw_metadata}
            elif isinstance(raw_metadata, dict):
                parsed_metadata = raw_metadata

            metadata = {
                key: value
                for key, value in document.items()
                if key
                not in {
                    "content",
                    "chunk",
                    "text",
                    "title",
                    "source",
                    "@search.score",
                    "id",
                    "metadata",
                }
            }
            if parsed_metadata:
                metadata.update(parsed_metadata)

            normalized.append(
                {
                    "id": document.get("id"),
                    "content": content,
                    "title": title,
                    "score": score,
                    "metadata": metadata or None,
                }
            )

        return normalized

    @staticmethod
    def _normalize_document(document: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure documents conform to the expected index schema."""

        normalized = dict(document)
        metadata = normalized.get("metadata")
        if isinstance(metadata, (dict, list)):
            normalized["metadata"] = json.dumps(metadata)
        return normalized
