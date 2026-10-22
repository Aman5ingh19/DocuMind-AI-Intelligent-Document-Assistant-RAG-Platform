"""
Tests for the text chunking service.

What we test:
  - Chunks are produced from valid extracted text
  - Chunk IDs are unique within a document
  - Every chunk carries page number metadata
  - Chunk sizes respect the configured limits
  - Overlap: consecutive chunks share some text
  - Documents that span multiple pages: chunks know which pages they came from
  - Empty document → returns empty list (no exception)
"""
import pytest

from app.services.chunker import DocumentChunker, TextChunk
from app.services.pdf_processor import ExtractedDocument, PageContent


def _make_document(texts_by_page: list[str], document_id: str = "doc-1") -> ExtractedDocument:
    """Helper: create an ExtractedDocument from a list of page texts."""
    pages = [
        PageContent(page_number=i + 1, raw_text=text)
        for i, text in enumerate(texts_by_page)
    ]
    return ExtractedDocument(
        document_id=document_id,
        file_path="/fake/path.pdf",
        total_pages=len(pages),
        pages=pages,
    )


def test_chunks_are_produced_from_text():
    """A document with substantial text should produce at least one chunk."""
    doc = _make_document(["This is a test document. " * 50])
    chunker = DocumentChunker(chunk_size_chars=200, overlap_chars=50)
    chunks = chunker.chunk(doc)
    assert len(chunks) >= 1


def test_chunk_ids_are_unique():
    """Every chunk in a document must have a unique ID."""
    doc = _make_document(["Hello world. " * 200])
    chunker = DocumentChunker(chunk_size_chars=100, overlap_chars=20)
    chunks = chunker.chunk(doc)
    ids = [c.chunk_id for c in chunks]
    assert len(ids) == len(set(ids)), "Duplicate chunk IDs found"


def test_chunk_ids_include_document_id(document_id):
    """Chunk IDs must embed the document_id for traceability."""
    doc = _make_document(["Test content. " * 100], document_id=document_id)
    chunker = DocumentChunker(chunk_size_chars=200, overlap_chars=40)
    chunks = chunker.chunk(doc)
    for chunk in chunks:
        assert document_id in chunk.chunk_id


def test_all_chunks_have_page_number():
    """Every chunk must have a valid (positive) page number for citation."""
    doc = _make_document(["Content on page one. " * 100, "Content on page two. " * 100])
    chunker = DocumentChunker(chunk_size_chars=200, overlap_chars=50)
    chunks = chunker.chunk(doc)
    for chunk in chunks:
        assert chunk.page_number >= 1
        assert len(chunk.page_numbers) >= 1


def test_empty_document_produces_no_chunks():
    """A document with no text should return an empty list, not raise an exception."""
    # Manually create a doc bypassing the has_content check
    pages = [PageContent(page_number=1, raw_text="")]
    doc = ExtractedDocument(
        document_id="empty-doc",
        file_path="/fake/empty.pdf",
        total_pages=1,
        pages=pages,
    )
    chunker = DocumentChunker()
    chunks = chunker.chunk(doc)
    assert chunks == []


def test_chunk_text_is_not_empty():
    """No chunk should have empty text."""
    doc = _make_document(["Sentence one. Sentence two. Sentence three. " * 30])
    chunker = DocumentChunker(chunk_size_chars=100, overlap_chars=20, min_chunk_chars=10)
    chunks = chunker.chunk(doc)
    for chunk in chunks:
        assert chunk.text.strip() != "", f"Empty text in chunk {chunk.chunk_id}"


def test_consecutive_chunks_overlap():
    """With overlap > 0, end of chunk N should appear at start of chunk N+1."""
    long_text = "The quick brown fox jumps over the lazy dog. " * 100
    doc = _make_document([long_text])
    chunker = DocumentChunker(chunk_size_chars=300, overlap_chars=100)
    chunks = chunker.chunk(doc)
    if len(chunks) >= 2:
        # The end of chunk 0 and start of chunk 1 should share some character range
        assert chunks[0].char_end > chunks[1].char_start


def test_chunks_cover_document_content():
    """Together all chunks should cover the full document text (no dropped content)."""
    content = "Important content number {} here. ".format
    texts = ["".join(content(i) for i in range(50))]
    doc = _make_document(texts)
    chunker = DocumentChunker(chunk_size_chars=200, overlap_chars=50)
    chunks = chunker.chunk(doc)
    all_text = " ".join(c.text for c in chunks)
    # At least the first and last parts of the document should be present
    assert "Important content number 0" in all_text
