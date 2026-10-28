"""PDF extraction, validation, chunking, and grounded text retrieval service."""

import io
import re
import math
import logging
from typing import List, Dict, Any, Tuple
from utils.errors import PDFProcessingError

logger = logging.getLogger(__name__)

# Check if PyMuPDF (fitz) is available; fallback to pypdf
PYMUPDF_AVAILABLE = False
try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    pass

import pypdf


class PDFService:
    """Handles PDF validation, page-aware text extraction, chunking, and local lexical retrieval."""

    def extract_text_by_pages(self, file_bytes: bytes, filename: str) -> List[Dict[str, Any]]:
        """Extracts text page-by-page from raw PDF bytes.
        
        Returns a list of dictionaries: [{'page_number': 1, 'text': '...'}]
        Detects encrypted, empty, and scanned PDFs without selectable text.
        """
        if not file_bytes or len(file_bytes) == 0:
            raise PDFProcessingError("The uploaded PDF file is empty.")

        pages_data = []

        # Try PyMuPDF first if available
        if PYMUPDF_AVAILABLE:
            try:
                doc = fitz.open(stream=file_bytes, filetype="pdf")
                if doc.is_encrypted:
                    raise PDFProcessingError(
                        f"The document '{filename}' is password-protected or encrypted. Please upload an unencrypted PDF."
                    )
                for page_idx in range(len(doc)):
                    page = doc[page_idx]
                    text = page.get_text() or ""
                    pages_data.append({"page_number": page_idx + 1, "text": text.strip()})
                doc.close()
            except PDFProcessingError:
                raise
            except Exception as e:
                logger.warning(f"PyMuPDF extraction failed, falling back to pypdf: {e}")
                pages_data = []

        # Fallback to pypdf
        if not pages_data:
            try:
                stream = io.BytesIO(file_bytes)
                reader = pypdf.PdfReader(stream)

                if reader.is_encrypted:
                    try:
                        # Attempt to decrypt with empty password in case of standard permissions
                        reader.decrypt("")
                    except Exception:
                        raise PDFProcessingError(
                            f"The document '{filename}' is password-protected or encrypted. Please upload an unencrypted PDF."
                        )

                for page_idx, page in enumerate(reader.pages):
                    try:
                        text = page.extract_text() or ""
                    except Exception:
                        text = ""
                    pages_data.append({"page_number": page_idx + 1, "text": text.strip()})
            except PDFProcessingError:
                raise
            except Exception as e:
                raise PDFProcessingError(
                    f"Unable to process the PDF '{filename}'. The file may be corrupted or malformed.",
                    technical_details=str(e),
                )

        if not pages_data:
            raise PDFProcessingError(f"No pages could be extracted from '{filename}'.")

        # Check for scanned PDF (no extractable text across all pages)
        total_text_length = sum(len(p["text"]) for p in pages_data)
        if total_text_length < 20:
            raise PDFProcessingError(
                f"The document '{filename}' appears to be a scanned image or contains no selectable text. "
                "The PDF Assistant requires text-based PDFs to search and answer questions."
            )

        return pages_data

    def chunk_document(
        self,
        pages_data: List[Dict[str, Any]],
        chunk_size_chars: int = 800,
        chunk_overlap_chars: int = 150,
    ) -> List[Dict[str, Any]]:
        """Splits page text into overlapping chunks while preserving page number boundaries."""
        chunks = []
        chunk_index = 0

        for page in pages_data:
            page_num = page["page_number"]
            text = page["text"]
            if not text:
                continue

            # Split page text into overlapping windows
            start = 0
            while start < len(text):
                end = min(start + chunk_size_chars, len(text))
                
                # If we're not at the very end, try not to cut words in half
                if end < len(text):
                    last_space = text.rfind(" ", start, end)
                    if last_space > start + (chunk_size_chars // 2):
                        end = last_space

                chunk_content = text[start:end].strip()
                if len(chunk_content) > 30:
                    chunks.append(
                        {
                            "chunk_index": chunk_index,
                            "page_start": page_num,
                            "page_end": page_num,
                            "chunk_text": chunk_content,
                        }
                    )
                    chunk_index += 1

                if end >= len(text):
                    break
                start = end - chunk_overlap_chars
                if start < 0:
                    start = 0

        return chunks

    def retrieve_relevant_chunks(
        self,
        query: str,
        chunks: List[Dict[str, Any]],
        top_k: int = 4,
    ) -> List[Dict[str, Any]]:
        """Performs lexical and BM25-style token matching to find top relevant chunks."""
        if not chunks or not query:
            return []

        # Tokenize query
        stop_words = {
            "the", "is", "at", "which", "on", "a", "an", "and", "or", "in", "for",
            "to", "of", "with", "what", "how", "why", "when", "where", "can", "do",
            "does", "explain", "describe", "tell", "me", "about"
        }
        raw_query_tokens = re.findall(r"\b[a-zA-Z0-9_]{2,}\b", query.lower())
        query_tokens = [t for t in raw_query_tokens if t not in stop_words]
        
        if not query_tokens:
            query_tokens = raw_query_tokens

        if not query_tokens:
            return chunks[:top_k]

        # Score each chunk
        scored_chunks = []
        for chunk in chunks:
            text = chunk.get("chunk_text", "").lower()
            tokens = re.findall(r"\b[a-zA-Z0-9_]{2,}\b", text)
            if not tokens:
                continue

            token_count = len(tokens)
            score = 0.0

            # Exact phrase bonus
            clean_query = query.lower().strip()
            if len(clean_query) > 5 and clean_query in text:
                score += 5.0

            # Frequency scoring
            for qt in query_tokens:
                occurrences = text.count(qt)
                if occurrences > 0:
                    # Term frequency with diminishing returns
                    tf = math.log(1.0 + occurrences)
                    score += tf * 1.5

            if score > 0.1:
                scored_chunks.append((score, chunk))

        # Sort descending by relevance score
        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored_chunks[:top_k]]


pdf_service = PDFService()
