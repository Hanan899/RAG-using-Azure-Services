"""REST API routes for chat and document operations."""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from app.models.schemas import ChatRequest, ChatResponse
from app.services.openai_service import AzureOpenAIService
from app.services.rag_service import RAGService
from app.services.search_service import (
    AzureSearchService,
    IndexConfigurationError,
    SearchServiceUnavailableError,
)
from app.config.config import settings
from app.utils.logging import get_logger
from app.utils.file_processor import (
    chunk_text_with_metadata,
    FormRecognizerConfigError,
    FormRecognizerServiceError,
    PDFExtractionError,
    extract_text_from_docx,
    extract_text_from_pdf,
    extract_text_from_txt,
)
from app.utils.prompt_templates import STRICT_RAG_SYSTEM_PROMPT

logger = get_logger(__name__)

router = APIRouter()
openai_service = AzureOpenAIService()
search_service = AzureSearchService()
rag_service = RAGService(
    search_service=search_service,
    openai_service=openai_service,
)

MAX_UPLOAD_BYTES = 50 * 1024 * 1024
SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".docx"}


def _chat_options(request: ChatRequest) -> Dict[str, Any]:
    """Build shared chat options for stream and non-stream calls."""

    return {
        "query": request.message,
        "top_k": request.top_k or 5,
        "temperature": request.temperature or 0.2,
        "max_tokens": request.max_tokens or 512,
    }


async def _generate_fallback_answer(request: ChatRequest) -> str:
    """Generate a complete non-stream response for SSE fallback."""

    result = await rag_service.process_query(**_chat_options(request))
    return str(result.get("answer") or "")


async def _safe_fallback_answer(request: ChatRequest) -> str | None:
    """Best-effort fallback that never raises inside the SSE generator."""

    try:
        return await _generate_fallback_answer(request)
    except Exception:
        logger.exception("Fallback non-stream response failed")
        return None


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Process chat query through the RAG pipeline."""

    try:
        result = await rag_service.process_query(**_chat_options(request))
        return ChatResponse(
            answer=result["answer"],
            sources=result["sources"],
            has_sufficient_context=result.get("has_sufficient_context", True),
            tokens_used=result.get("tokens_used", 0),
            suggested_actions=result.get("suggested_actions"),
        )
    except SearchServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except IndexConfigurationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Chat request failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest) -> EventSourceResponse:
    """Stream chat responses via server-sent events."""
    # Compatibility endpoint: primary production rendering should use /api/chat
    # so responses always pass backend normalization and source-footer enforcement.

    async def event_generator():
        if not settings.enable_streaming:
            fallback_answer = await _safe_fallback_answer(request)
            if fallback_answer is not None:
                yield {"data": fallback_answer}
            else:
                yield {"event": "error", "data": "Streaming disabled and fallback failed."}
            return

        try:
            options = _chat_options(request)
            context_result = await rag_service.process_query(
                **options,
                generate_answer=False,
            )
            if not context_result.get("has_sufficient_context", True):
                yield {"data": context_result["answer"]}
                return

            context_documents = context_result.get("context_documents", [])
            context = rag_service.format_context(context_documents)
            strict_prompt = STRICT_RAG_SYSTEM_PROMPT.format(
                context=context, question=request.message
            )

            streamed_any = False
            async for chunk in openai_service.chat_completion_stream(
                query="",
                conversation_history=[],
                context_documents=None,
                system_prompt=strict_prompt,
                temperature=options["temperature"],
                max_tokens=options["max_tokens"],
            ):
                streamed_any = True
                yield {"data": chunk}
            if not streamed_any:
                fallback_answer = await _safe_fallback_answer(request)
                if fallback_answer is not None:
                    yield {"event": "fallback", "data": fallback_answer}
        except IndexConfigurationError as exc:
            yield {"event": "error", "data": str(exc)}
            fallback_answer = await _safe_fallback_answer(request)
            if fallback_answer is not None:
                yield {"event": "fallback", "data": fallback_answer}
        except SearchServiceUnavailableError as exc:
            yield {"event": "error", "data": str(exc)}
            fallback_answer = await _safe_fallback_answer(request)
            if fallback_answer is not None:
                yield {"event": "fallback", "data": fallback_answer}
        except Exception as exc:
            logger.exception("Streaming chat failed")
            yield {"event": "error", "data": str(exc)}
            fallback_answer = await _safe_fallback_answer(request)
            if fallback_answer is not None:
                yield {"event": "fallback", "data": fallback_answer}

    return EventSourceResponse(event_generator())


@router.post("/documents/upload")
async def upload_document(file: UploadFile = File(...)) -> JSONResponse:
    """Upload a document, chunk it, and store embeddings in Azure Search."""

    filename = file.filename or ""
    extension = "." + filename.split(".")[-1].lower() if "." in filename else ""
    if extension not in SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    file_bytes = await file.read()
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large")

    if extension == ".pdf":
        try:
            text = await extract_text_from_pdf(file_bytes)
        except FormRecognizerConfigError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except FormRecognizerServiceError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except PDFExtractionError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    elif extension == ".docx":
        text = extract_text_from_docx(file_bytes)
    else:
        text = extract_text_from_txt(file_bytes)

    if not text.strip():
        raise HTTPException(status_code=400, detail="No text extracted from file")

    chunk_records = chunk_text_with_metadata(text, chunk_size=500)
    chunks = [str(item["content"]) for item in chunk_records]
    if not chunks:
        raise HTTPException(status_code=400, detail="No content to index")

    embeddings = await openai_service.generate_embeddings_batch(chunks)

    parent_id = str(uuid.uuid4())
    documents: List[Dict[str, Any]] = []
    for idx, chunk in enumerate(chunks):
        section_name = str(chunk_records[idx].get("section_name") or "").strip()
        metadata: Dict[str, Any] = {
            "parent_id": parent_id,
            "filename": filename,
            "source": filename,
            "chunk_index": idx,
            "uploaded_at": int(time.time()),
        }
        if section_name:
            metadata["section_name"] = section_name
            metadata["section"] = section_name

        documents.append(
            {
                "id": str(uuid.uuid4()),
                "title": filename,
                "content": chunk,
                "metadata": metadata,
                "embedding": embeddings[idx],
            }
        )

    try:
        await search_service.upload_documents(documents)
    except SearchServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except IndexConfigurationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return JSONResponse(
        {
            "message": "Document uploaded",
            "document_count": len(documents),
            "chunk_count": len(documents),
            "file_count": 1,
            "filename": filename,
            "parent_id": parent_id,
        }
    )


@router.get("/documents")
async def list_documents(top: int | None = None) -> JSONResponse:
    """List documents in the Azure Search index."""

    try:
        stats = await search_service.get_index_stats()
        indexed_chunk_count = int(stats.get("document_count") or 0)
        if top is None:
            results = await search_service.list_all_documents()
        else:
            results = await search_service.hybrid_search(
                query_text="*", query_embedding=None, top_k=top
            )
    except SearchServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except IndexConfigurationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    grouped: Dict[str, Dict[str, Any]] = {}
    for doc in results:
        metadata = doc.get("metadata") or {}
        parent_id = metadata.get("parent_id") or metadata.get("filename") or doc.get("id")
        title = metadata.get("filename") or doc.get("title") or "Document"
        if parent_id not in grouped:
            grouped[parent_id] = {
                "id": parent_id,
                "title": title,
                "metadata": {"chunk_count": 0},
            }
        grouped[parent_id]["metadata"]["chunk_count"] += 1

    documents = list(grouped.values())
    chunk_count = indexed_chunk_count or len(results)
    return JSONResponse(
        {
            "documents": documents,
            "count": len(documents),
            "file_count": len(documents),
            "chunk_count": chunk_count,
        }
    )


@router.delete("/documents/{document_id}")
async def delete_document(document_id: str) -> JSONResponse:
    """Delete a document by ID."""

    try:
        results = await search_service.hybrid_search(
            query_text="*", query_embedding=None, top_k=1000
        )
        chunk_ids = []
        for doc in results:
            metadata = doc.get("metadata") or {}
            if metadata.get("parent_id") == document_id:
                if doc.get("id"):
                    chunk_ids.append(doc["id"])

        if chunk_ids:
            await search_service.delete_documents(chunk_ids)
        else:
            # Fallback: delete by ID directly for backwards compatibility.
            await search_service.delete_documents([document_id])
    except SearchServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except IndexConfigurationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return JSONResponse({"message": "Document deleted", "document_id": document_id})


@router.get("/health")
async def health() -> JSONResponse:
    """Check service connectivity and return latency metrics."""

    status: Dict[str, Any] = {"status": "ok"}

    search_start = time.perf_counter()
    try:
        await search_service.hybrid_search(query_text="*", query_embedding=None, top_k=1)
        status["azure_search"] = "ok"
    except IndexConfigurationError as exc:
        status["azure_search"] = f"error: {exc}"
    except Exception as exc:
        status["azure_search"] = f"error: {exc}"
    status["azure_search_latency_ms"] = int((time.perf_counter() - search_start) * 1000)

    openai_start = time.perf_counter()
    try:
        await openai_service.chat_completion(query="ping", conversation_history=[])
        status["azure_openai"] = "ok"
    except Exception as exc:
        status["azure_openai"] = f"error: {exc}"
    status["azure_openai_latency_ms"] = int((time.perf_counter() - openai_start) * 1000)

    return JSONResponse(status)
