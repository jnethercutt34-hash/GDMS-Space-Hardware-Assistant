"""Datasheet PDF file store — saves uploaded PDFs to disk for later retrieval.

Files are stored in backend/data/datasheets/ with deduplication by content hash.
Thin wrapper around FileStore.
"""
import os
from typing import Optional

from services.file_store import FileStore

_STORE_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "datasheets")
_store = FileStore(_STORE_DIR, ".pdf", binary=True)


def save(pdf_bytes: bytes, original_filename: str) -> str:
    """Save a PDF to the store. Returns the stored filename."""
    return _store.save(pdf_bytes, original_filename)


def get_path(filename: str) -> Optional[str]:
    """Return the full filesystem path for a stored datasheet, or None."""
    return _store.get_path(filename)


def exists(filename: str) -> bool:
    """Check if a datasheet file exists in the store."""
    return _store.exists(filename)
