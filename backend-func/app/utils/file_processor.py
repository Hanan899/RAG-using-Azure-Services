"""Utilities for extracting and chunking text from uploaded files."""

from __future__ import annotations
import io

import re
from typing import Dict, List, Optional

from azure.ai.formrecognizer.aio import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import AzureError
from docx import Document

from app.config.config import settings


class PDFExtractionError(RuntimeError):
    """Base error for PDF text extraction failures."""


class FormRecognizerConfigError(PDFExtractionError):
    """Raised when Form Recognizer endpoint/key are not configured."""


class FormRecognizerServiceError(PDFExtractionError):
    """Raised when Azure Form Recognizer request fails."""


async def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract text from a PDF using Azure Form Recognizer prebuilt-layout."""

    endpoint = settings.azure_form_recognizer_endpoint.strip()
    key = settings.azure_form_recognizer_key.strip()
    if not endpoint or not key:
        raise FormRecognizerConfigError(
            "PDF extraction requires AZURE_FORM_RECOGNIZER_ENDPOINT and AZURE_FORM_RECOGNIZER_KEY."
        )

    client: Optional[DocumentAnalysisClient] = None
    try:
        client = DocumentAnalysisClient(
            endpoint=endpoint,
            credential=AzureKeyCredential(key),
        )
        poller = await client.begin_analyze_document("prebuilt-layout", file_bytes)
        result = await poller.result()
    except AzureError as exc:
        raise FormRecognizerServiceError(
            "Azure Form Recognizer request failed while extracting PDF text."
        ) from exc
    except Exception as exc:  # pragma: no cover - defensive
        raise FormRecognizerServiceError(
            "Unexpected error during Azure Form Recognizer PDF extraction."
        ) from exc
    finally:
        if client is not None:
            await client.close()

    text = (getattr(result, "content", None) or "").strip()
    if not text:
        page_blocks: List[str] = []
        for page in getattr(result, "pages", []) or []:
            lines = []
            for line in getattr(page, "lines", []) or []:
                content = str(getattr(line, "content", "")).strip()
                if content:
                    lines.append(content)
            if lines:
                page_blocks.append("\n".join(lines))
        text = "\n\n".join(page_blocks).strip()

    text = _normalize_extracted_text(text)
    if not text:
        raise PDFExtractionError("No text extracted from PDF by Azure Form Recognizer.")
    return text


def extract_text_from_docx(file_bytes: bytes) -> str:
    """Extract text from a DOCX file."""

    document = Document(io.BytesIO(file_bytes))
    return "\n".join(paragraph.text for paragraph in document.paragraphs)


def extract_text_from_txt(file_bytes: bytes) -> str:
    """Extract text from a plain text file."""

    return file_bytes.decode("utf-8", errors="ignore")


def _normalize_extracted_text(text: str) -> str:
    """Normalize extraction output while preserving paragraph boundaries."""

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = normalized.replace("\u200b", "").replace("\ufeff", "")
    normalized = re.sub(r"[ \t]+\n", "\n", normalized)
    normalized = re.sub(r"\n[ \t]+\n", "\n\n", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def _normalize_line(line: str) -> str:
    """Normalize whitespace for a single line."""

    return " ".join(line.replace("\u00a0", " ").split()).strip()


def _detect_heading(line: str) -> Optional[str]:
    """Detect section-like headings from a line of text."""

    candidate = _normalize_line(line)
    if not candidate:
        return None

    if candidate[0] in {"-", "*", "•"}:
        return None

    if len(candidate) > 140:
        return None

    stripped = candidate.rstrip(":")
    word_count = len(stripped.split())
    if word_count == 0 or word_count > 14:
        return None

    lower = stripped.lower()
    if re.match(r"^(part|section|chapter)\s+\d+[a-z]?\s*:", lower):
        return stripped

    if re.match(r"^\d+(?:\.\d+)*[\.)]?\s+[A-Za-z].*$", stripped):
        return stripped

    if stripped.isupper() and word_count <= 10:
        return stripped

    return None


def chunk_text_with_metadata(text: str, chunk_size: int = 500) -> List[Dict[str, Optional[str]]]:
    """Split text into chunks and attach inferred section metadata."""

    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")

    lines = text.splitlines()
    if not lines:
        return []

    chunks: List[Dict[str, Optional[str]]] = []
    chunk_words: List[str] = []
    chunk_section: Optional[str] = None
    current_section: Optional[str] = None

    def flush_chunk() -> None:
        nonlocal chunk_words, chunk_section
        if not chunk_words:
            return
        chunks.append(
            {
                "content": " ".join(chunk_words).strip(),
                "section_name": chunk_section,
            }
        )
        chunk_words = []
        chunk_section = None

    for raw_line in lines:
        line = _normalize_line(raw_line)
        if not line:
            continue

        heading = _detect_heading(line)
        if heading:
            current_section = heading

        words = line.split()
        idx = 0
        while idx < len(words):
            if not chunk_words:
                chunk_section = current_section

            remaining = chunk_size - len(chunk_words)
            take = words[idx : idx + remaining]
            chunk_words.extend(take)
            idx += len(take)

            if len(chunk_words) >= chunk_size:
                flush_chunk()

    flush_chunk()
    return [item for item in chunks if item.get("content")]


def chunk_text(text: str, chunk_size: int = 500) -> List[str]:
    """Split text into chunks of up to chunk_size words."""

    chunk_records = chunk_text_with_metadata(text, chunk_size=chunk_size)
    return [str(record["content"]) for record in chunk_records]
