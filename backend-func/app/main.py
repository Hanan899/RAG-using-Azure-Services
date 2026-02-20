"""FastAPI application entry point."""

import time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config.config import settings
from app.routes.chat_routes import router as chat_router

# Create the FastAPI application instance.
app = FastAPI(title="RAG Chatbot API")

# Simple request logging middleware with latency tracking.
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.perf_counter()
    response = await call_next(request)
    duration_ms = int((time.perf_counter() - start_time) * 1000)
    print(f"{request.method} {request.url.path} {duration_ms}ms")
    return response


# Global exception handler for unexpected errors.
@app.exception_handler(Exception)
async def unhandled_exception_handler(_request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"detail": str(exc)})

# Enable CORS for local development; restrict origins in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=settings.allowed_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routes under a common prefix.
app.include_router(chat_router, prefix="/api", tags=["chat"])
