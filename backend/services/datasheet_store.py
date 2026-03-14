"""Datasheet PDF file store — saves uploaded PDFs to disk for later retrieval.

Files are stored in backend/data/datasheets/ with deduplication by content hash.
"""
import hashlib
import os
import re
from typing import Optional

_STORE_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "datasheets")


def _sanitize(filename: str) -> str:
    """Strip unsafe characters from a filename, preserving the .pdf extension."""
    name = os.path.basename(filename)
    name = re.sub(r"[^\w\-. ()]+", "_", name)
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    return name


def save(pdf_bytes: bytes, original_filename: str) -> str:
    """Save a PDF to the store. Returns the stored filename.

    If a file with the same name already exists and has different content,
    a short hash suffix is appended to avoid collisions.
    """
    os.makedirs(_STORE_DIR, exist_ok=True)
    name = _sanitize(original_filename)
    dest = os.path.join(_STORE_DIR, name)

    # If file already exists with same content, just return the name
    if os.path.exists(dest):
        with open(dest, "rb") as f:
            existing_hash = hashlib.md5(f.read()).hexdigest()[:8]
        new_hash = hashlib.md5(pdf_bytes).hexdigest()[:8]
        if existing_hash == new_hash:
            return name
        # Different content — add hash suffix
        base, ext = os.path.splitext(name)
        name = f"{base}_{new_hash}{ext}"
        dest = os.path.join(_STORE_DIR, name)

    with open(dest, "wb") as f:
        f.write(pdf_bytes)

    return name


def get_path(filename: str) -> Optional[str]:
    """Return the full filesystem path for a stored datasheet, or None."""
    name = _sanitize(filename)
    path = os.path.join(_STORE_DIR, name)
    if os.path.isfile(path):
        return path
    return None


def exists(filename: str) -> bool:
    """Check if a datasheet file exists in the store."""
    return get_path(filename) is not None
