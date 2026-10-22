"""
FastAPI application entrypoint.

This module creates and configures the FastAPI application instance.
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import get_settings

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Application lifespan (startup / shutdown hooks)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Runs startup logic before the server accepts requests, and cleanup on shutdown.
    Using asynccontextmanager is the modern FastAPI pattern (replaces on_event).
    """
    settings = get_settings()

    # Ensure data directories exist
    Path(settings.CHROMA_PERSIST_DIR).mkdir(parents=True, exist_ok=True)
    Path(settings.DOCUMENT_STORAGE_PATH).mkdir(parents=True, exist_ok=True)

    # Eagerly initialise the vector store (and embedding provider) at startup
    # so the first request is not slow.
    from app.services.vector_store import get_vector_store
    vector_store = get_vector_store()
    logger.info("AI service started. Vector store ready.")
    logger.info(
        "Config: LLM_PROVIDER=%s EMBEDDING_PROVIDER=%s",
        settings.LLM_PROVIDER,
        settings.EMBEDDING_PROVIDER,
    )

    yield  # Application runs between yield and cleanup below

    logger.info("AI service shutting down.")


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "Internal AI microservice for the Document Assistant application. "
            "Handles PDF extraction, vector indexing, and RAG question answering."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # CORS – only allow requests from the ASP.NET Core backend in production.
    # In development, allow localhost origins for testing with tools like Postman.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5000", "http://localhost:5001", "http://backend:8080"],
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type", "X-Internal-Api-Key"],
    )

    # Register route handlers
    app.include_router(router)

    return app


app = create_app()
