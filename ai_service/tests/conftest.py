"""
pytest configuration and shared fixtures for the AI service test suite.

Key design decisions:
  - All tests use the "mock" provider by default so they never make external API calls.
  - We patch settings at the module level using monkeypatch/environment variables.
  - Tests are fully isolated: each test gets a fresh in-memory vector store.
"""
import os
import sys
import tempfile
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Environment setup (must happen before any app imports)
# ---------------------------------------------------------------------------

os.environ.setdefault("LLM_PROVIDER", "mock")
os.environ.setdefault("EMBEDDING_PROVIDER", "mock")
os.environ.setdefault("INTERNAL_API_KEY", "test-internal-key")


@pytest.fixture(scope="session")
def sample_pdf_path(tmp_path_factory) -> Path:
    """
    Create a minimal valid PDF file for testing.
    Uses raw PDF syntax to avoid a dependency on a PDF generation library.
    """
    pdf_content = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj

2 0 obj
<< /Type /Pages /Kids [3 0 R 4 0 R] /Count 2 >>
endobj

3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]
/Contents 5 0 R /Resources << /Font << /F1 6 0 R >> >> >>
endobj

4 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]
/Contents 7 0 R /Resources << /Font << /F1 6 0 R >> >> >>
endobj

5 0 obj
<< /Length 90 >>
stream
BT /F1 12 Tf 72 720 Td (Unit 3 covers data structures: arrays, linked lists, trees.) Tj
72 700 Td (This is page one content for testing.) Tj ET
endstream
endobj

7 0 obj
<< /Length 70 >>
stream
BT /F1 12 Tf 72 720 Td (Page two content. Arrays have O(1) access time.) Tj ET
endstream
endobj

6 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj

xref
0 8
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000266 00000 n
0000000417 00000 n
0000000560 00000 n
0000000633 00000 n

trailer
<< /Size 8 /Root 1 0 R >>
startxref
734
%%EOF"""
    tmp_dir = tmp_path_factory.mktemp("pdfs")
    pdf_file = tmp_dir / "test_document.pdf"
    pdf_file.write_bytes(pdf_content)
    return pdf_file


@pytest.fixture
def temp_chroma_dir(tmp_path) -> str:
    """Provide a unique temporary directory for ChromaDB to ensure test isolation."""
    return str(tmp_path / "chroma")


@pytest.fixture
def document_id() -> str:
    return "test-doc-00000000-0000-0000-0000-000000000001"
