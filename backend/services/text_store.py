"""Extracted PDF text file store — saves full datasheet text alongside stored PDFs.

Files are stored in backend/data/texts/ with deduplication by content hash.
The stored filename mirrors the source PDF filename with .pdf replaced by .txt.
"""
import hashlib
import os
import re
from typing import Optional

_STORE_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "texts")


def _sanitize(source_pdf_filename: str) -> str:
    """Derive a safe .txt filename from the source PDF filename."""
    name = os.path.basename(source_pdf_filename)
    name = re.sub(r"[^\w\-. ()]+", "_", name)
    # Strip .pdf extension (case-insensitive) and append .txt
    if name.lower().endswith(".pdf"):
        name = name[:-4]
    name += ".txt"
    return name


def save(text: str, source_pdf_filename: str) -> str:
    """Save extracted text to the store. Returns the stored filename.

    If a file with the same name already exists and has different content,
    a short hash suffix is appended to avoid collisions.
    """
    os.makedirs(_STORE_DIR, exist_ok=True)
    name = _sanitize(source_pdf_filename)
    dest = os.path.join(_STORE_DIR, name)

    text_bytes = text.encode("utf-8")

    if os.path.exists(dest):
        existing_hash = hashlib.md5(open(dest, "rb").read()).hexdigest()[:8]
        new_hash = hashlib.md5(text_bytes).hexdigest()[:8]
        if existing_hash == new_hash:
            return name
        # Different content — add hash suffix before .txt
        base, ext = os.path.splitext(name)
        name = f"{base}_{new_hash}{ext}"
        dest = os.path.join(_STORE_DIR, name)

    with open(dest, "w", encoding="utf-8") as f:
        f.write(text)

    return name


def get_path(txt_filename: str) -> Optional[str]:
    """Return the full filesystem path for a stored text file, or None."""
    name = _sanitize(txt_filename) if txt_filename.lower().endswith(".pdf") else os.path.basename(txt_filename)
    path = os.path.join(_STORE_DIR, name)
    if os.path.isfile(path):
        return path
    return None


def exists(txt_filename: str) -> bool:
    """Check if a text file exists in the store."""
    return get_path(txt_filename) is not None
