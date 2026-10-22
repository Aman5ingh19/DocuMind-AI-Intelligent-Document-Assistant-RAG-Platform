"""
Embedding generation abstraction.

Why an abstraction layer?
  Different embedding providers (OpenAI, Gemini, local Sentence-Transformers)
  have different APIs and different dimension sizes. This module hides all of
  that behind a single `embed_texts()` function. The provider is selected at
  startup from the EMBEDDING_PROVIDER environment variable.

Cost note:
  - "mock"  → zero cost, zero latency, returns random unit vectors. Use in tests.
  - "sentence-transformers" → runs locally on CPU/GPU. Free but needs ~100 MB model.
  - "openai" → charged per 1000 tokens. Check pricing.openai.com.
"""
from __future__ import annotations

import logging
import math
import random
from typing import Protocol

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# ---------------------------------------------------------------------------
# Protocol (interface) for type-safe embedding providers
# ---------------------------------------------------------------------------

class EmbeddingProvider(Protocol):
    """Any object implementing this interface can be used as an embedding provider."""

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Return a list of embedding vectors, one per input text."""
        ...

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query string."""
        ...

    @property
    def dimension(self) -> int:
        """Output vector dimension."""
        ...


# ---------------------------------------------------------------------------
# Mock provider (for testing – no external calls)
# ---------------------------------------------------------------------------

class MockEmbeddingProvider:
    """
    Returns deterministic pseudo-random unit vectors.
    Uses a seeded RNG so the same text always gets the same vector within a
    session, enabling reproducible tests.
    """

    def __init__(self, dimension: int = 384) -> None:
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    def _make_vector(self, text: str) -> list[float]:
        rng = random.Random(hash(text) & 0xFFFFFFFF)
        vec = [rng.gauss(0, 1) for _ in range(self._dimension)]
        magnitude = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / magnitude for x in vec]

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self._make_vector(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._make_vector(text)


# ---------------------------------------------------------------------------
# OpenAI provider
# ---------------------------------------------------------------------------

class OpenAIEmbeddingProvider:
    """Wraps the OpenAI Embeddings API."""

    def __init__(self, model: str = "text-embedding-3-small", dimension: int = 1536) -> None:
        self._model = model
        self._dimension = dimension
        try:
            from openai import OpenAI
            self._client = OpenAI(api_key=settings.OPENAI_API_KEY)
        except ImportError as exc:
            raise RuntimeError("openai package not installed. Run: pip install openai") from exc

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        response = self._client.embeddings.create(input=texts, model=self._model)
        return [item.embedding for item in response.data]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]


# ---------------------------------------------------------------------------
# Sentence-Transformers provider (free, local)
# ---------------------------------------------------------------------------

class SentenceTransformerProvider:
    """Uses the sentence-transformers library for local, free embeddings."""

    def __init__(self, model: str = "all-MiniLM-L6-v2") -> None:
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(model)
            self._dimension = self._model.get_sentence_embedding_dimension()
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers not installed. Run: pip install sentence-transformers"
            ) from exc

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        vectors = self._model.encode(texts, convert_to_numpy=True)
        return vectors.tolist()

    def embed_query(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]


# ---------------------------------------------------------------------------
# Factory function
# ---------------------------------------------------------------------------

_provider_instance: EmbeddingProvider | None = None


def get_embedding_provider() -> EmbeddingProvider:
    """
    Return (and cache) the configured embedding provider singleton.

    Selected by the EMBEDDING_PROVIDER environment variable:
      - "mock"                → MockEmbeddingProvider (default for dev/tests)
      - "openai"              → OpenAIEmbeddingProvider
      - "sentence-transformers" → SentenceTransformerProvider
    """
    global _provider_instance  # noqa: PLW0603
    if _provider_instance is not None:
        return _provider_instance

    provider_name = settings.EMBEDDING_PROVIDER.lower()
    logger.info("Initialising embedding provider: %s", provider_name)

    if provider_name == "mock":
        _provider_instance = MockEmbeddingProvider(dimension=384)
    elif provider_name == "openai":
        if not settings.OPENAI_API_KEY:
            raise EnvironmentError(
                "OPENAI_API_KEY is not set. "
                "Set it in your .env file or environment variables."
            )
        _provider_instance = OpenAIEmbeddingProvider(
            model=settings.EMBEDDING_MODEL,
            dimension=settings.EMBEDDING_DIMENSION,
        )
    elif provider_name == "sentence-transformers":
        _provider_instance = SentenceTransformerProvider(model=settings.EMBEDDING_MODEL)
    else:
        raise ValueError(
            f"Unknown EMBEDDING_PROVIDER: '{provider_name}'. "
            "Valid values: mock | openai | sentence-transformers"
        )

    return _provider_instance
