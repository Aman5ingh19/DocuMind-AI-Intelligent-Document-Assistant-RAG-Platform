"""
Pydantic request and response schemas for the AI service API.

These form the contract between ASP.NET Core and the Python AI service.
Pydantic automatically validates incoming request data and serialises responses.
"""
from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Process Document
# ---------------------------------------------------------------------------

class ProcessDocumentRequest(BaseModel):
    """Sent by .NET backend to trigger PDF extraction + vectorisation."""
    document_id: str = Field(..., description="UUID of the document (from MySQL)")
    file_path: str = Field(..., description="Absolute path to the stored PDF file")

    @field_validator("file_path")
    @classmethod
    def no_path_traversal(cls, v: str) -> str:
        """Reject obvious path-traversal attempts in the file path."""
        if ".." in v:
            raise ValueError("Path traversal detected in file_path")
        return v


class ProcessDocumentResponse(BaseModel):
    """Returned to .NET backend after successful processing."""
    document_id: str
    total_pages: int
    chunk_count: int
    status: str = "Completed"


# ---------------------------------------------------------------------------
# Query (RAG question answering)
# ---------------------------------------------------------------------------

class ConversationMessage(BaseModel):
    """A single turn of conversation history for follow-up context."""
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str


class QueryRequest(BaseModel):
    """Sent by .NET backend to perform vector search + LLM inference."""
    question: str = Field(..., min_length=1, max_length=4096)
    document_ids: list[str] = Field(..., min_length=1)
    conversation_history: list[ConversationMessage] = Field(
        default_factory=list,
        description="Recent messages for follow-up context (last 6 turns at most)",
    )


class Citation(BaseModel):
    """A single source citation backing the LLM answer."""
    document_id: str
    page_number: int
    snippet: str = Field(..., description="Verbatim excerpt from the source chunk")
    relevance_score: float = Field(..., ge=0.0, le=1.0)


class QueryResponse(BaseModel):
    """Full answer with grounded citations."""
    answer: str
    citations: list[Citation]
    model_used: str


# ---------------------------------------------------------------------------
# Delete Document
# ---------------------------------------------------------------------------

class DeleteDocumentResponse(BaseModel):
    """Confirmation of vector deletion."""
    success: bool
    deleted_chunks: int
    document_id: str


# ---------------------------------------------------------------------------
# Health Check
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    """Simple readiness/liveness probe response."""
    status: str
    version: str
    vector_db: str
    llm_provider: str
    embedding_provider: str
    details: dict[str, Any] = Field(default_factory=dict)
