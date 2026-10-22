"""
Application configuration loaded from environment variables.
All secrets (API keys, internal tokens) must be supplied via environment variables.
No secrets are ever committed to source control.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central configuration object for the AI service.
    Pydantic-settings automatically reads values from environment variables
    (and from a .env file when present).
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # -----------------------------------------------------------------
    # Service Identity
    # -----------------------------------------------------------------
    APP_NAME: str = "AI Document Assistant – AI Service"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # -----------------------------------------------------------------
    # Internal Security
    # Shared secret between ASP.NET Core API and this service.
    # Set a long random string in production.
    # -----------------------------------------------------------------
    INTERNAL_API_KEY: str = "change-me-in-production-use-a-long-random-string"

    # -----------------------------------------------------------------
    # LLM Provider Selection
    # Valid values: "openai" | "gemini" | "groq" | "ollama" | "mock"
    # Use "mock" for testing without any API key or network calls.
    # -----------------------------------------------------------------
    LLM_PROVIDER: str = "mock"
    LLM_MODEL: str = "gpt-4o-mini"            # Provider-specific model name
    LLM_BASE_URL: str | None = None           # Override base URL (Ollama / Azure / proxy)
    LLM_TEMPERATURE: float = 0.1             # Low temperature for factual grounding
    LLM_MAX_TOKENS: int = 1024
    LLM_REQUEST_TIMEOUT_SECONDS: int = 60

    # -----------------------------------------------------------------
    # API Keys (never hardcoded – read from environment only)
    # -----------------------------------------------------------------
    OPENAI_API_KEY: str | None = None
    GEMINI_API_KEY: str | None = None
    GROQ_API_KEY: str | None = None

    # -----------------------------------------------------------------
    # Embedding Provider
    # Valid values: "openai" | "sentence-transformers" | "mock"
    # "sentence-transformers" is free/local – good for development.
    # -----------------------------------------------------------------
    EMBEDDING_PROVIDER: str = "mock"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSION: int = 1536          # Must match the chosen model output dim

    # -----------------------------------------------------------------
    # ChromaDB Vector Store
    # -----------------------------------------------------------------
    CHROMA_PERSIST_DIR: str = "./data/chroma_db"
    CHROMA_COLLECTION_NAME: str = "document_chunks"

    # -----------------------------------------------------------------
    # PDF Processing
    # -----------------------------------------------------------------
    CHUNK_SIZE_TOKENS: int = 500             # Approximate tokens per chunk
    CHUNK_OVERLAP_TOKENS: int = 100          # Token overlap between consecutive chunks
    MAX_RETRIEVAL_RESULTS: int = 8           # Max chunks returned per query

    # -----------------------------------------------------------------
    # File Storage
    # Shared mount path between .NET API and Python AI service.
    # In Docker the host path is volume-mounted at this location.
    # -----------------------------------------------------------------
    DOCUMENT_STORAGE_PATH: str = "./data/documents"


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton Settings instance."""
    return Settings()
