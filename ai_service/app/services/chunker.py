"""
Text chunking service.

Strategy: Recursive character-based splitting with a token budget.

Why overlapping chunks?
  A chunk boundary might split a sentence mid-way. By overlapping consecutive
  chunks (e.g. 100 tokens of overlap) we ensure every sentence appears in at
  least one full chunk, improving retrieval quality.

Each chunk carries metadata that lets us cite exact page numbers later.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from app.services.pdf_processor import ExtractedDocument, PageContent

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class TextChunk:
    """A single chunk of text ready for embedding."""
    chunk_id: str                # unique: "{document_id}_chunk_{idx:05d}"
    document_id: str
    page_number: int             # page the chunk *starts* on (1-indexed)
    page_numbers: list[int]      # all pages spanned (for cross-page chunks)
    text: str
    char_start: int              # character offset in the full document text
    char_end: int


# ---------------------------------------------------------------------------
# Main chunker
# ---------------------------------------------------------------------------

class DocumentChunker:
    """
    Splits an ExtractedDocument into overlapping TextChunks.

    Parameters
    ----------
    chunk_size_chars : int
        Target chunk size in characters. We use characters instead of tokens
        because a simple character count avoids a heavy tokeniser dependency
        while still giving predictable chunk sizes.
        Rule of thumb: 1 token ≈ 4 characters → 500 tokens ≈ 2000 chars.
    overlap_chars : int
        How many characters of the previous chunk to repeat at the start of
        the next chunk.
    min_chunk_chars : int
        Chunks shorter than this are discarded (usually trailing whitespace).
    """

    def __init__(
        self,
        chunk_size_chars: int = 2000,
        overlap_chars: int = 400,
        min_chunk_chars: int = 100,
    ) -> None:
        self.chunk_size_chars = chunk_size_chars
        self.overlap_chars = overlap_chars
        self.min_chunk_chars = min_chunk_chars

    def chunk(self, document: ExtractedDocument) -> list[TextChunk]:
        """
        Split the document into overlapping text chunks, tracking page provenance.

        Returns
        -------
        list[TextChunk]
            Ordered list of chunks with metadata for vector-store ingestion.
        """
        # Build a merged view of the document text with page boundary markers.
        full_text, page_boundaries = self._merge_pages(document.pages)

        if not full_text.strip():
            logger.warning("document_id=%s produced empty merged text", document.document_id)
            return []

        raw_chunks = self._sliding_window_split(full_text)

        chunks: list[TextChunk] = []
        for idx, (char_start, char_end, text) in enumerate(raw_chunks):
            page_nums = self._pages_for_span(char_start, char_end, page_boundaries)
            chunks.append(
                TextChunk(
                    chunk_id=f"{document.document_id}_chunk_{idx:05d}",
                    document_id=document.document_id,
                    page_number=page_nums[0],
                    page_numbers=page_nums,
                    text=text,
                    char_start=char_start,
                    char_end=char_end,
                )
            )

        logger.info(
            "Chunked document_id=%s into %d chunks (chunk_size=%d overlap=%d)",
            document.document_id,
            len(chunks),
            self.chunk_size_chars,
            self.overlap_chars,
        )
        return chunks

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _merge_pages(self, pages: list[PageContent]) -> tuple[str, list[tuple[int, int, int]]]:
        """
        Concatenate all page texts into one string and record where each page
        starts and ends.

        Returns
        -------
        full_text : str
        page_boundaries : list of (page_number, char_start, char_end)
        """
        parts: list[str] = []
        boundaries: list[tuple[int, int, int]] = []
        cursor = 0

        for page in pages:
            text = page.cleaned_text
            if not text:
                continue
            start = cursor
            parts.append(text)
            cursor += len(text)
            # Add a newline separator between pages
            parts.append("\n\n")
            cursor += 2
            end = cursor
            boundaries.append((page.page_number, start, end))

        return "".join(parts), boundaries

    def _sliding_window_split(self, text: str) -> list[tuple[int, int, str]]:
        """
        Produce overlapping character windows over `text`.

        Returns list of (char_start, char_end, chunk_text).
        We try to split at sentence boundaries ('. ', '? ', '! ') within a
        tolerance of ±200 chars to avoid cutting mid-sentence.
        """
        results: list[tuple[int, int, str]] = []
        start = 0
        text_len = len(text)

        while start < text_len:
            end = min(start + self.chunk_size_chars, text_len)

            # Try to snap the boundary to a sentence end
            if end < text_len:
                snap_zone = text[max(end - 200, start) : end + 200]
                best_split = -1
                for sep in (". ", ".\n", "? ", "! ", ".\n\n"):
                    idx = snap_zone.rfind(sep)
                    if idx != -1 and idx > best_split:
                        best_split = idx + len(sep) - 1
                if best_split != -1:
                    end = max(end - 200, start) + best_split + 1

            chunk_text = text[start:end].strip()
            if len(chunk_text) >= self.min_chunk_chars:
                results.append((start, end, chunk_text))

            if end >= text_len:
                break
            start = max(start + 1, end - self.overlap_chars)

        return results

    def _pages_for_span(
        self,
        char_start: int,
        char_end: int,
        boundaries: list[tuple[int, int, int]],
    ) -> list[int]:
        """
        Return the sorted list of page numbers that overlap with [char_start, char_end).
        Always returns at least [1] so citations always have a page.
        """
        pages = [
            page_num
            for page_num, page_start, page_end in boundaries
            if page_start < char_end and page_end > char_start
        ]
        return sorted(set(pages)) or [1]
