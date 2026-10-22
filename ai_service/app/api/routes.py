"""
FastAPI route handlers for the AI service.

Security: Every endpoint (except /health) requires the X-Internal-API-Key header
to match the INTERNAL_API_KEY setting. This prevents the AI service from being
called directly by external clients, bypassing ASP.NET Core authorization.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Header, status

from app.core.config import get_settings
from app.models.schemas import (
    DeleteDocumentResponse,
    HealthResponse,
    ProcessDocumentRequest,
    ProcessDocumentResponse,
    QueryRequest,
    QueryResponse,
)
from app.services.chunker import DocumentChunker
from app.services.pdf_processor import PDFProcessingError, extract_pdf
from app.services.rag_service import answer_question
from app.services.vector_store import get_vector_store

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter()


# ---------------------------------------------------------------------------
# Internal API key dependency
# ---------------------------------------------------------------------------

def verify_internal_api_key(x_internal_api_key: str = Header(...)) -> None:
    """
    FastAPI dependency that validates the shared internal API key.

    Raises HTTP 401 if the key is missing or incorrect.
    """
    if x_internal_api_key != settings.INTERNAL_API_KEY:
        logger.warning("Rejected request: invalid internal API key")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal API key.",
        )


# ---------------------------------------------------------------------------
# Health Check (no auth required – used by Docker health checks)
# ---------------------------------------------------------------------------

@router.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check() -> HealthResponse:
    """Readiness and liveness probe."""
    vector_store = get_vector_store()
    try:
        # Quick connectivity check – count items in the collection
        count = vector_store._collection.count()
        vector_db_status = f"connected (total_chunks={count})"
    except Exception as exc:  # noqa: BLE001
        vector_db_status = f"error: {exc}"

    return HealthResponse(
        status="ok",
        version=settings.APP_VERSION,
        vector_db=vector_db_status,
        llm_provider=settings.LLM_PROVIDER,
        embedding_provider=settings.EMBEDDING_PROVIDER,
        details={
            "llm_model": settings.LLM_MODEL,
            "embedding_model": settings.EMBEDDING_MODEL,
            "chroma_persist_dir": settings.CHROMA_PERSIST_DIR,
        },
    )


# ---------------------------------------------------------------------------
# Process Document (Extract → Chunk → Embed → Index)
# ---------------------------------------------------------------------------

@router.post(
    "/api/v1/process-document",
    response_model=ProcessDocumentResponse,
    status_code=status.HTTP_200_OK,
    tags=["Documents"],
    dependencies=[Depends(verify_internal_api_key)],
)
async def process_document(request: ProcessDocumentRequest) -> ProcessDocumentResponse:
    """
    Called by ASP.NET Core when a new PDF has been saved to storage.
    Extracts text, chunks it, generates embeddings, and indexes in ChromaDB.
    """
    logger.info(
        "Processing document: document_id=%s file_path=%s",
        request.document_id,
        request.file_path,
    )

    # 1. Extract text from PDF
    try:
        extracted = extract_pdf(request.document_id, request.file_path)
    except PDFProcessingError as exc:
        logger.error("PDF extraction failed: document_id=%s error=%s", request.document_id, exc)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    # 2. Chunk the extracted text
    chunker = DocumentChunker(
        chunk_size_chars=settings.CHUNK_SIZE_TOKENS * 4,   # ~4 chars per token
        overlap_chars=settings.CHUNK_OVERLAP_TOKENS * 4,
    )
    chunks = chunker.chunk(extracted)

    if not chunks:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No text chunks could be produced from this document.",
        )

    # 3. Embed and index chunks
    vector_store = get_vector_store()
    indexed_count = vector_store.index_chunks(chunks)

    logger.info(
        "Document processed: document_id=%s total_pages=%d chunks=%d",
        request.document_id,
        extracted.total_pages,
        indexed_count,
    )

    return ProcessDocumentResponse(
        document_id=request.document_id,
        total_pages=extracted.total_pages,
        chunk_count=indexed_count,
        status="Completed",
    )


# ---------------------------------------------------------------------------
# Query (RAG Question Answering)
# ---------------------------------------------------------------------------

@router.post(
    "/api/v1/query",
    response_model=QueryResponse,
    tags=["RAG"],
    dependencies=[Depends(verify_internal_api_key)],
)
async def query_documents(request: QueryRequest) -> QueryResponse:
    """
    Perform vector search and LLM-grounded question answering.
    The .NET API has already verified that the user owns all document_ids.
    """
    logger.info(
        "RAG query: question_len=%d document_ids=%s",
        len(request.question),
        request.document_ids,
    )

    result = answer_question(
        question=request.question,
        document_ids=request.document_ids,
        conversation_history=request.conversation_history,
    )

    return QueryResponse(
        answer=result.answer,
        citations=result.citations,
        model_used=result.model_used,
    )


# ---------------------------------------------------------------------------
# Delete Document (remove vectors from ChromaDB)
# ---------------------------------------------------------------------------

@router.delete(
    "/api/v1/documents/{document_id}",
    response_model=DeleteDocumentResponse,
    tags=["Documents"],
    dependencies=[Depends(verify_internal_api_key)],
)
async def delete_document(document_id: str) -> DeleteDocumentResponse:
    """
    Delete all vector store records for a document.
    Called by ASP.NET Core when a user deletes a document.
    """
    logger.info("Deleting vectors for document_id=%s", document_id)
    vector_store = get_vector_store()
    try:
        deleted_count = vector_store.delete_document(document_id)
    except Exception as exc:  # noqa: BLE001
        logger.error("Vector deletion failed for document_id=%s: %s", document_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete document vectors: {exc}",
        ) from exc

    return DeleteDocumentResponse(
        success=True,
        deleted_chunks=deleted_count,
        document_id=document_id,
    )
