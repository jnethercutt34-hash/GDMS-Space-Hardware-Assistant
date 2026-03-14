"""Base class for content-addressed file stores with MD5 deduplication.

Subclasses specify the store directory and file extension. The base class
handles sanitization, dedup, save, and lookup.

Architecture:
    FileStore (this file)
      ├── datasheet_store.py  (PDFs  → data/datasheets/, binary)
      └── text_store.py       (texts → data/texts/, text/utf-8)
"""
import hashlib
import os
import re
from typing import Optional


class FileStore:
    """Content-addressed file store with MD5-based deduplication.

    Parameters:
        store_dir: Absolute path to the storage directory.
        extension: File extension including dot (e.g. '.pdf', '.txt').
        binary:    If True, save/read as bytes; if False, as UTF-8 text.
    """

    def __init__(self, store_dir: str, extension: str, *, binary: bool = True):
        self._store_dir = store_dir
        self._extension = extension.lower()
        self._binary = binary

    # ------------------------------------------------------------------
    # Filename sanitization
    # ------------------------------------------------------------------

    def sanitize(self, filename: str) -> str:
        """Produce a safe filename with the correct extension.

        - Strips directory components (prevents path traversal)
        - Replaces unsafe characters with underscores
        - Ensures the file has the correct extension
        """
        name = os.path.basename(filename)
        name = re.sub(r"[^\w\-. ()]+", "_", name)

        # Strip any existing extension that matches a known source extension
        # (e.g. .pdf when producing .txt), then apply our extension.
        base, ext = os.path.splitext(name)
        if ext.lower() != self._extension:
            # If the existing extension isn't ours, strip it and add ours
            name = base + self._extension
        # If it already has the right extension, keep it as-is.
        # Handle case where name ended up empty after sanitization
        if not base.strip("_. "):
            name = "unnamed" + self._extension

        return name

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------

    def save(self, content, original_filename: str) -> str:
        """Save content to the store. Returns the stored filename.

        Args:
            content: bytes (if binary=True) or str (if binary=False).
            original_filename: Original filename for naming the stored file.

        If a file with the same name and identical content exists, returns
        the existing filename without re-writing. If same name but different
        content, appends an 8-char MD5 hash suffix to avoid collision.
        """
        os.makedirs(self._store_dir, exist_ok=True)
        name = self.sanitize(original_filename)
        dest = os.path.join(self._store_dir, name)

        content_bytes = content if self._binary else content.encode("utf-8")
        new_hash = hashlib.md5(content_bytes).hexdigest()[:8]

        if os.path.exists(dest):
            with open(dest, "rb") as f:
                existing_hash = hashlib.md5(f.read()).hexdigest()[:8]
            if existing_hash == new_hash:
                return name
            # Different content — add hash suffix before extension
            base, ext = os.path.splitext(name)
            name = f"{base}_{new_hash}{ext}"
            dest = os.path.join(self._store_dir, name)

        mode = "wb" if self._binary else "w"
        kwargs = {} if self._binary else {"encoding": "utf-8"}
        with open(dest, mode, **kwargs) as f:
            f.write(content)

        return name

    def get_path(self, filename: str) -> Optional[str]:
        """Return the full filesystem path for a stored file, or None."""
        name = self.sanitize(filename)
        path = os.path.join(self._store_dir, name)
        if os.path.isfile(path):
            return path
        return None

    def exists(self, filename: str) -> bool:
        """Check if a file exists in the store."""
        return self.get_path(filename) is not None
