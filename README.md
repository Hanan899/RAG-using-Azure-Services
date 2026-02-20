# RAG Chatbot with Azure AI Search and Azure OpenAI

This repository contains a full Retrieval-Augmented Generation (RAG) app with:
- A backend in `backend-func/` (FastAPI app hosted through Azure Functions, plus direct Uvicorn support for local development).
- A Streamlit frontend in `frontend/` with pages for chat, document management, session history, and settings.

## Architecture
```mermaid
flowchart LR
  UI[Streamlit Frontend] --> API[/api endpoints]
  API --> RAG[RAG Service]
  RAG --> EMB[Azure OpenAI Embeddings]
  RAG --> DI[Document Intelligence]
  RAG --> SRCH[Azure AI Search]
  RAG --> CHAT[Azure OpenAI Chat]
```

## Current Repository Layout
```text
backend-func/
  app/
    config/         # Settings + credentials loader
    models/         # Pydantic schemas
    routes/         # /api routes
    services/       # OpenAI, Search, RAG services
    utils/          # Prompt templates, file processing, logging
  function_app.py   # Azure Functions v2 ASGI bridge
  host.json
  requirements.txt

frontend/
  app.py            # Chat page
  pages/
    documents.py
    session_history.py
    settings.py
  components/
  utils/
  requirements.txt
  tests/

tests/
  test_config.py    # legacy config test
```

## Key Features
- Hybrid retrieval (keyword + vector) against Azure AI Search.
- Optional semantic query mode in Azure Search.
- Strict RAG answering with source footer normalization.
- PDF extraction via Azure Form Recognizer (`prebuilt-layout`), plus TXT and DOCX support.
- Upload chunking with section detection (500-word chunks).
- SSE streaming endpoint (`/api/chat/stream`) for compatibility.
- Streamlit multi-page UI with custom chat rendering and markdown sanitization.

## Prerequisites
- Python 3.10+
- Azure AI Search
- Azure OpenAI (chat + embedding deployments)
- Azure Form Recognizer (required for PDF uploads)
- Azure Functions Core Tools (`func`) for local Functions hosting (optional)

## Installation
From repository root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend-func/requirements.txt
pip install -r frontend/requirements.txt
pip install pytest
```

## Configuration
The backend currently reads settings from a Python dictionary in:
- `backend-func/app/config/credentials.py`

`backend-func/app/config/config.py` builds `settings` from that dict. There is no `.env` loading in backend code right now.

Required setting keys:
- `AZURE_SEARCH_SERVICE_ENDPOINT`
- `AZURE_SEARCH_ADMIN_KEY`
- `AZURE_SEARCH_INDEX_NAME`
- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_API_KEY`
- `AZURE_OPENAI_DEPLOYMENT_NAME`
- `AZURE_OPENAI_API_VERSION`
- `AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME`

Optional setting keys:
- `AZURE_FORM_RECOGNIZER_ENDPOINT`
- `AZURE_FORM_RECOGNIZER_KEY`
- `EMBEDDING_DIMENSIONS` (default parsing fallback: `1536`)
- `AZURE_SEARCH_USE_SEMANTIC` (`true`/`false`)
- `AZURE_SEARCH_AUTO_CREATE_INDEX` (`true`/`false`)
- `MINIMUM_RELEVANCE_SCORE` (float)
- `ENABLE_STREAMING` (`true`/`false`)
- `ALLOWED_ORIGINS` (comma-separated list or `*`)

Frontend configuration:
- `BACKEND_URL` (loaded from environment via `python-dotenv`)
- Default in frontend code is currently `https://ragchatbotbackend.azurewebsites.net`.

For local backend testing, set:
- `BACKEND_URL=http://127.0.0.1:8000` when running Uvicorn.
- `BACKEND_URL=http://127.0.0.1:7071` when running Azure Functions host.

## Run the Backend
Option 1 (direct FastAPI via Uvicorn):

```bash
uvicorn app.main:app --reload --app-dir backend-func
```

Option 2 (Azure Functions host):

```bash
cd backend-func
func start
```

## Run the Frontend
From repository root:

```bash
streamlit run frontend/app.py
```

## API Endpoints
### `GET /api/health`
Returns service health and latency fields:
- `status`
- `azure_search`
- `azure_search_latency_ms`
- `azure_openai`
- `azure_openai_latency_ms`

### `POST /api/chat`
Body:
```json
{
  "message": "Question text",
  "history": [{"role": "user", "content": "Hi"}],
  "top_k": 5,
  "temperature": 0.2,
  "max_tokens": 512
}
```
Response:
```json
{
  "answer": "**Answer** ...",
  "sources": [
    {
      "id": "doc-id",
      "title": "filename.pdf",
      "relevance_score": 0.87,
      "excerpt": "snippet",
      "metadata": {}
    }
  ],
  "has_sufficient_context": true,
  "tokens_used": 123,
  "suggested_actions": null
}
```

### `POST /api/chat/stream`
Server-sent events stream; falls back to non-stream answer when needed.

### `POST /api/documents/upload`
- Multipart upload field: `file`
- Supported: `.pdf`, `.txt`, `.docx`
- Max upload size: 50 MB

### `GET /api/documents`
- Aggregated by uploaded file (`parent_id`) with file and chunk counts.
- Optional query param: `top` (limits search results path).

### `DELETE /api/documents/{document_id}`
Deletes all chunks matching a file-level `parent_id` when found.

## RAG Behavior
- Query embedding is generated with Azure OpenAI (with retry).
- Hybrid search is executed in Azure AI Search.
- Results are filtered by `MINIMUM_RELEVANCE_SCORE` and reranked by score.
- If no relevant context remains, response is a no-context answer with suggested actions.
- When context exists, a strict prompt is built (`STRICT_RAG_SYSTEM_PROMPT`).
- The answer is normalized to markdown and prefixed with `**Answer**`.
- Inline source citations are removed, then one consolidated `Sources:` footer is appended.
- `history` is accepted in request payloads, but current `/api/chat` route logic does not pass it into generation.

## Frontend Pages
- `frontend/app.py` (Chat): chat input, rendered user/assistant bubbles, sanitized markdown, token usage tracked in message metadata.
- `frontend/pages/documents.py`: upload file, display file/chunk metrics, bar chart by chunk count, delete documents.
- `frontend/pages/session_history.py`: shows current in-session message history and counts.
- `frontend/pages/settings.py`: controls for `temperature`, `max_tokens`, `top_k`, plus health check button.

## Testing
Install test dependency:
```bash
pip install pytest
```

Run frontend tests:
```bash
python -m pytest frontend/tests -q
```

Run all tests:
```bash
python -m pytest -q
```

Note:
- `tests/test_config.py` references `backend/` import paths, while this repo uses `backend-func/`. If you run the full suite, update that test or `PYTHONPATH` accordingly.

## Common Errors
- `400`: unsupported file type or no extractable text.
- `413`: uploaded file too large.
- `502`: Form Recognizer request failure.
- `503`: Azure Search connectivity issue or missing Form Recognizer config for PDF extraction.
- `409`: index configuration conflict (for example embedding dimension mismatch with existing index).

## Security Note
- The current backend configuration uses hardcoded credential values in `backend-func/app/config/credentials.py`.
- Do not commit real secrets in source control.
- Rotate any exposed keys and move to secure secret storage (for example environment variables, Azure Key Vault, or App Settings) before production use.
