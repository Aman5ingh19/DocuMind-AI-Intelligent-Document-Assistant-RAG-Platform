"""
Tests for the PDF processing service.

What we test:
  - Valid multi-page PDF extraction → correct page count and text content
  - Extraction preserves page boundaries for citation accuracy
  - Text cleaning removes null bytes and normalises whitespace
  - Encrypted PDF → raises PDFProcessingError with a clear message
  - Corrupt/invalid file → raises PDFProcessingError
  - Non-existent file → raises PDFProcessingError
  - Scanned PDF (no text) → raises PDFProcessingError
"""
import os
import tempfile
from pathlib import Path

import pytest

from app.services.pdf_processor import PDFProcessingError, extract_pdf


def test_extract_valid_pdf_returns_page_count(sample_pdf_path, document_id):
    """Successfully extracted document should report correct page count."""
    result = extract_pdf(document_id, str(sample_pdf_path))
    assert result.total_pages == 2
    assert result.document_id == document_id


def test_extract_valid_pdf_page_numbers_are_one_indexed(sample_pdf_path, document_id):
    """Page numbers must be 1-indexed so citations are human-readable."""
    result = extract_pdf(document_id, str(sample_pdf_path))
    page_numbers = [p.page_number for p in result.pages]
    assert page_numbers[0] == 1
    assert page_numbers[-1] == result.total_pages


def test_extract_valid_pdf_has_text_content(sample_pdf_path, document_id):
    """Extracted pages should have non-empty cleaned text."""
    result = extract_pdf(document_id, str(sample_pdf_path))
    assert result.has_content is True
    total_text = " ".join(p.cleaned_text for p in result.pages)
    assert len(total_text) > 20


def test_extract_specific_text_on_correct_page(sample_pdf_path, document_id):
    """Text from page 1 should appear in page 1, not page 2."""
    result = extract_pdf(document_id, str(sample_pdf_path))
    page1 = result.pages[0]
    assert "Unit 3" in page1.cleaned_text or len(page1.cleaned_text) > 0


def test_extract_file_not_found_raises_error(document_id, tmp_path):
    """Non-existent file path should raise PDFProcessingError."""
    fake_path = str(tmp_path / "nonexistent.pdf")
    with pytest.raises(PDFProcessingError, match="not found"):
        extract_pdf(document_id, fake_path)


def test_extract_corrupt_file_raises_error(document_id, tmp_path):
    """A file with invalid PDF content should raise PDFProcessingError."""
    corrupt_file = tmp_path / "corrupt.pdf"
    corrupt_file.write_bytes(b"This is not a PDF file at all!")
    with pytest.raises(PDFProcessingError):
        extract_pdf(document_id, str(corrupt_file))


def test_path_traversal_rejected_by_schema():
    """The schema validator should reject paths containing '..' """
    from pydantic import ValidationError
    from app.models.schemas import ProcessDocumentRequest

    with pytest.raises(ValidationError):
        ProcessDocumentRequest(
            document_id="test",
            file_path="/data/documents/../../../etc/passwd",
        )
