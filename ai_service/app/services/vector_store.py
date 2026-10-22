"""
ChromaDB vector store interface.

Why ChromaDB?
  - Runs embedded (no separate server needed for development)
  - Persists to disk automatically
  - Supports metadata filtering (we filter by document_id so users can only
    retrieve their own documents)
  - Simple Python API with no complex setup

In production you can switch to chroma in client/server mode or swap the
vector store entirely by reimplementing the VectorStore interface below.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from app.core.config import get_settings
from app.services.chunker import TextChunk
from app.services.embeddings import get_embedding_provider

logger = logging.getLogger(__name__)
settings = get_settings()


# ---------------------------------------------------------------------------
# Data types returned from search
# ---------------------------------------------------------------------------

@dataclass
class SearchResult:
    """A retrieved chunk with metadata and relevance score."""
    chunk_id: str
    document_id: str
    page_number: int
    page_numbers: list[int]
    text: str
    relevance_score: float          # 0.0 (not relevant) → 1.0 (perfect match)


# ---------------------------------------------------------------------------
# ChromaDB vector store wrapper
# ---------------------------------------------------------------------------

class VectorStore:
    """
    Wraps ChromaDB with document-scoped operations.

    All methods use the document_id as a metadata filter to ensure
    one user's documents cannot bleed into another's retrieval results.
    (Cross-user isolation is enforced at the .NET API layer, but defence-in-depth
    requires us to always filter by document_id here too.)
    """

    def __init__(self) -> None:
        try:
            import chromadb
        except ImportError as exc:
            raise RuntimeError(
                "chromadb package not installed. Run: pip install chromadb"
            ) from exc

        self._chroma = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
        self._collection = self._chroma.get_or_create_collection(
            name=settings.CHROMA_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},  # cosine similarity
        )
        self._embedder = get_embedding_provider()
        logger.info(
            "VectorStore initialised: collection=%s persist_dir=%s",
            settings.CHROMA_COLLECTION_NAME,
            settings.CHROMA_PERSIST_DIR,
        )

    def index_chunks(self, chunks: list[TextChunk]) -> int:
        """
        Embed and upsert a list of chunks into the vector store.

        Using upsert (not add) so that reprocessing a document is idempotent:
        existing chunks are overwritten, not duplicated.

        Returns the number of chunks indexed.
        """
        if not chunks:
            return 0

        texts = [c.text for c in chunks]
        embeddings = self._embedder.embed_texts(texts)

        ids = [c.chunk_id for c in chunks]
        metadatas: list[dict[str, Any]] = [
            {
                "document_id": c.document_id,
                "page_number": c.page_number,
                "page_numbers": ",".join(str(p) for p in c.page_numbers),
                "char_start": c.char_start,
                "char_end": c.char_end,
            }
            for c in chunks
        ]

        self._collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )

        logger.info(
            "Indexed %d chunks for document_ids=%s",
            len(chunks),
            list({c.document_id for c in chunks}),
        )
        return len(chunks)

    def search(
        self,
        query: str,
        document_ids: list[str],
        n_results: int | None = None,
    ) -> list[SearchResult]:
        """
        Find the most relevant chunks for a query, restricted to specific documents.

        Args:
            query:        Natural-language question.
            document_ids: Only consider chunks belonging to these documents.
                          (The .NET API guarantees the caller owns all of these.)
            n_results:    Number of chunks to return.

        Returns:
            SearchResult list ordered by descending relevance.
        """
        if not document_ids:
            return []

        n_results = n_results or settings.MAX_RETRIEVAL_RESULTS

        query_embedding = self._embedder.embed_query(query)

        # Build a ChromaDB where clause to filter by document ownership.
        if len(document_ids) == 1:
            where: dict[str, Any] = {"document_id": {"$eq": document_ids[0]}}
        else:
            where = {"document_id": {"$in": document_ids}}

        try:
            results = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("ChromaDB query failed: %s", exc)
            return []

        hits: list[SearchResult] = []
        documents_list = results.get("documents") or [[]]
        metadatas_list = results.get("metadatas") or [[]]
        distances_list = results.get("distances") or [[]]
        ids_list = results.get("ids") or [[]]

        for chunk_id, doc, meta, dist in zip(
            ids_list[0],
            documents_list[0],
            metadatas_list[0],
            distances_list[0],
        ):
            # ChromaDB cosine distance: 0 = identical, 2 = opposite.
            # Convert to similarity score 0–1.
            similarity = max(0.0, min(1.0, 1.0 - dist / 2.0))
            page_numbers_str = meta.get("page_numbers", str(meta.get("page_number", 1)))
            page_numbers = [int(p) for p in page_numbers_str.split(",") if p.isdigit()]
            hits.append(
                SearchResult(
                    chunk_id=chunk_id,
                    document_id=meta.get("document_id", ""),
                    page_number=int(meta.get("page_number", 1)),
                    page_numbers=page_numbers or [1],
                    text=doc,
                    relevance_score=similarity,
                )
            )

        return hits

    def delete_document(self, document_id: str) -> int:
        """
        Remove all chunks belonging to a document.

        Returns the number of deleted chunks.
        """
        try:
            existing = self._collection.get(
                where={"document_id": {"$eq": document_id}},
                include=[],
            )
            ids_to_delete = existing.get("ids", [])
            if ids_to_delete:
                self._collection.delete(ids=ids_to_delete)
            logger.info(
                "Deleted %d chunks for document_id=%s", len(ids_to_delete), document_id
            )
            return len(ids_to_delete)
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to delete document_id=%s from vector store: %s", document_id, exc)
            raise

    def document_chunk_count(self, document_id: str) -> int:
        """Return how many chunks are currently indexed for a document."""
        try:
            result = self._collection.get(
                where={"document_id": {"$eq": document_id}},
                include=[],
            )
            return len(result.get("ids", []))
        except Exception:  # noqa: BLE001
            return 0


# ---------------------------------------------------------------------------
# Singleton factory
# ---------------------------------------------------------------------------

_vector_store_instance: VectorStore | None = None


def get_vector_store() -> VectorStore:
    """Return the application-scoped VectorStore singleton."""
    global _vector_store_instance  # noqa: PLW0603
    if _vector_store_instance is None:
        _vector_store_instance = VectorStore()
    return _vector_store_instance
