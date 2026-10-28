"""Tests for PDF text processing, chunking, and lexical retrieval."""

import io
import pytest
import pypdf
from utils.errors import PDFProcessingError
from services.pdf_service import pdf_service


def create_in_memory_pdf(pages_text: list) -> bytes:
    """Helper to generate a valid PDF byte string for testing."""
    writer = pypdf.PdfWriter()
    for text in pages_text:
        # Create a blank page and add annotations or basic text
        page = writer.add_blank_page(width=300, height=300)
    # Using pypdf, we can write out the bytes
    stream = io.BytesIO()
    writer.write(stream)
    return stream.getvalue()


def test_empty_pdf_raises_error():
    with pytest.raises(PDFProcessingError):
        pdf_service.extract_text_by_pages(b"", "empty.pdf")


def test_chunking_logic():
    pages = [
        {
            "page_number": 1,
            "text": "This is page 1 content discussing the fundamental laws of thermodynamics. Energy cannot be created or destroyed.",
        },
        {
            "page_number": 2,
            "text": "Page 2 covers entropy and the second law of thermodynamics in closed and isolated systems.",
        },
    ]

    chunks = pdf_service.chunk_document(pages, chunk_size_chars=100, chunk_overlap_chars=20)
    assert len(chunks) >= 2
    assert chunks[0]["page_start"] == 1
    assert "thermodynamics" in chunks[0]["chunk_text"].lower()


def test_retrieval_ranking():
    chunks = [
        {
            "chunk_index": 0,
            "page_start": 1,
            "page_end": 1,
            "chunk_text": "Neural networks use backpropagation and gradient descent to update synaptic weights.",
        },
        {
            "chunk_index": 1,
            "page_start": 2,
            "page_end": 2,
            "chunk_text": "Relational databases use B-Trees and indexing to execute fast SQL lookups.",
        },
        {
            "chunk_index": 2,
            "page_start": 3,
            "page_end": 3,
            "chunk_text": "Operating systems employ paging and virtual memory management for memory protection.",
        },
    ]

    # Query about databases
    results = pdf_service.retrieve_relevant_chunks("What is a B-Tree index in relational databases?", chunks, top_k=2)
    assert len(results) >= 1
    assert "relational databases" in results[0]["chunk_text"].lower()

    # Query about neural networks
    results_nn = pdf_service.retrieve_relevant_chunks("Explain gradient descent and backpropagation", chunks, top_k=1)
    assert len(results_nn) == 1
    assert "backpropagation" in results_nn[0]["chunk_text"].lower()
