"""
PDF text extraction service using PyMuPDF (fitz).

Why PyMuPDF?
  - Very fast (C++ underneath)
  - Preserves exact page boundaries so we can cite page numbers
  - Handles most real-world PDF quirks (rotated pages, multi-column, etc.)
  - Does NOT run embedded JavaScript – safe for untrusted uploads

Limitations acknowledged:
  - Scanned PDFs (pure images) produce empty text → caller receives ProcessingError
  - Encrypted PDFs → ProcessingError with clear message
  - Corrupted PDFs → ProcessingError with clear message
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class PageContent:
    """Text extracted from a single PDF page."""
    page_number: int          # 1-indexed
    raw_text: str
    cleaned_text: str = field(default="", init=False)

    def __post_init__(self) -> None:
        self.cleaned_text = _clean_text(self.raw_text)


@dataclass
class ExtractedDocument:
    """Full extraction result for a PDF file."""
    document_id: str
    file_path: str
    total_pages: int
    pages: list[PageContent]
    is_scanned: bool = False

    @property
    def has_content(self) -> bool:
        return any(p.cleaned_text.strip() for p in self.pages)


class PDFProcessingError(Exception):
    """Raised when a PDF cannot be processed (corrupt, encrypted, scanned, etc.)."""


def extract_pdf(document_id: str, file_path: str) -> ExtractedDocument:
    """
    Open and extract text from a PDF, page by page.

    Args:
        document_id: UUID string used to identify this document in the vector store.
        file_path:   Absolute path to the PDF file.

    Returns:
        ExtractedDocument with per-page text and a cleaned version.

    Raises:
        PDFProcessingError: If the file cannot be opened or produces no extractable text.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:
        raise RuntimeError(
            "PyMuPDF is not installed. Run: pip install pymupdf"
        ) from exc

    path = Path(file_path)
    if not path.exists():
        raise PDFProcessingError(f"File not found: {file_path}")
    if not path.is_file():
        raise PDFProcessingError(f"Path is not a file: {file_path}")

    logger.info("Starting PDF extraction: document_id=%s file=%s", document_id, file_path)

    try:
        doc = fitz.open(str(path))
    except fitz.FileDataError as exc:
        raise PDFProcessingError(f"Corrupt or unreadable PDF: {exc}") from exc
    except Exception as exc:  # noqa: BLE001
        raise PDFProcessingError(f"Failed to open PDF: {exc}") from exc

    # Check encryption
    if doc.is_encrypted:
        doc.close()
        raise PDFProcessingError(
            "PDF is encrypted. Please provide an unencrypted file."
        )

    pages: list[PageContent] = []
    total_pages = doc.page_count

    for page_index in range(total_pages):
        page = doc[page_index]
        raw_text = page.get_text("text")  # type: ignore[attr-defined]
        pages.append(PageContent(page_number=page_index + 1, raw_text=raw_text))

    doc.close()

    extracted = ExtractedDocument(
        document_id=document_id,
        file_path=file_path,
        total_pages=total_pages,
        pages=pages,
    )

    # Warn and flag scanned documents
    if not extracted.has_content:
        extracted.is_scanned = True
        logger.warning(
            "No text content found in PDF – it may be a scanned/image-only PDF. "
            "document_id=%s pages=%d",
            document_id,
            total_pages,
        )
        raise PDFProcessingError(
            "No extractable text found. The PDF appears to be scanned (image-only). "
            "OCR support is not available in this version."
        )

    total_chars = sum(len(p.cleaned_text) for p in pages)
    logger.info(
        "Extraction complete: document_id=%s pages=%d total_chars=%d",
        document_id,
        total_pages,
        total_chars,
    )
    return extracted


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

_WHITESPACE_RE = re.compile(r"\s+")
_NULL_BYTE_RE = re.compile(r"\x00")
_HYPHEN_LINEBREAK_RE = re.compile(r"-\n(\w)")   # "hyphen-\nnewline" word joins


def _clean_text(text: str) -> str:
    """
    Clean raw text extracted from a PDF page.

    Steps:
      1. Remove null bytes (common in some PDF encodings)
      2. Rejoin words hyphenated across line breaks
      3. Collapse excessive whitespace into single spaces / newlines
      4. Strip leading/trailing whitespace
    """
    if not text:
        return ""

    text = _NULL_BYTE_RE.sub("", text)
    text = _HYPHEN_LINEBREAK_RE.sub(r"\1", text)

    # Preserve paragraph breaks (double-newline) while collapsing single newlines
    paragraphs = re.split(r"\n{2,}", text)
    paragraphs = [_WHITESPACE_RE.sub(" ", p).strip() for p in paragraphs]
    paragraphs = [p for p in paragraphs if p]

    return "\n\n".join(paragraphs)
