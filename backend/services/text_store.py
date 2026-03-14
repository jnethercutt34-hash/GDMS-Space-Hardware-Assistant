"""Extracted PDF text file store — saves full datasheet text alongside stored PDFs.

Files are stored in backend/data/texts/ with deduplication by content hash.
The stored filename mirrors the source PDF filename with .pdf replaced by .txt.
Thin wrapper around FileStore.
"""
import os
from typing import Optional

from services.file_store import FileStore

_STORE_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "texts")
_store = FileStore(_STORE_DIR, ".txt", binary=False)


def save(text: str, source_pdf_filename: str) -> str:
    """Save extracted text to the store. Returns the stored filename."""
    return _store.save(text, source_pdf_filename)


def get_path(txt_filename: str) -> Optional[str]:
    """Return the full filesystem path for a stored text file, or None."""
    return _store.get_path(txt_filename)


def exists(txt_filename: str) -> bool:
    """Check if a text file exists in the store."""
    return _store.exists(txt_filename)
