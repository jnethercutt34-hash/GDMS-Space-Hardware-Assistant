"""Base class for thread-safe, JSON-file-backed record stores with caching.

Provides load/save with threading.Lock, an in-memory cache that is
invalidated on every write, and graceful handling of corrupted files.

Architecture:
    JsonStore (this file)
      ├── part_library.py       (library.json — parts keyed by Part_Number)
      └── block_diagram_store.py (diagrams.json — diagrams keyed by id)

Cache invalidation:
    ┌──────────┐       ┌───────────┐       ┌──────────┐
    │  _load() │──────▶│  _cache   │──────▶│  caller   │
    └──────────┘       └───────────┘       └──────────┘
         ▲                    │
         │              invalidated
         │              on every _save()
    ┌──────────┐              │
    │  _save() │◀─────────────┘
    └──────────┘
"""
import json
import logging
import os
import threading
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class JsonStore:
    """Thread-safe JSON file store with in-memory read cache.

    Parameters:
        path: Absolute path to the JSON file.
    """

    def __init__(self, path: str):
        self._path = path
        self._lock = threading.Lock()
        self._cache: Optional[List[Dict[str, Any]]] = None

    # ------------------------------------------------------------------
    # Core I/O (internal)
    # ------------------------------------------------------------------

    def _load(self) -> List[Dict[str, Any]]:
        """Load records from disk, using cache if available."""
        if self._cache is not None:
            return self._cache

        if not os.path.exists(self._path):
            self._cache = []
            return self._cache

        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            logger.error(
                "Failed to load %s: %s — returning empty list. "
                "The corrupted file has NOT been deleted.",
                self._path, exc,
            )
            self._cache = []
            return self._cache

        if not isinstance(data, list):
            logger.error(
                "Expected a JSON array in %s, got %s — returning empty list.",
                self._path, type(data).__name__,
            )
            self._cache = []
            return self._cache

        self._cache = data
        return self._cache

    def _save(self, records: List[Dict[str, Any]]) -> None:
        """Write records to disk and update the cache."""
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2, ensure_ascii=False)
        self._cache = records

    def _invalidate_cache(self) -> None:
        """Force next _load() to read from disk."""
        self._cache = None

    # ------------------------------------------------------------------
    # Public read API
    # ------------------------------------------------------------------

    def get_all(self) -> List[Dict[str, Any]]:
        """Return all records."""
        return list(self._load())

    def get_by_key(self, key_field: str, value: str) -> Optional[Dict[str, Any]]:
        """Find a single record where record[key_field] == value."""
        for record in self._load():
            if record.get(key_field) == value:
                return record
        return None

    # ------------------------------------------------------------------
    # Public write API (all acquire _lock)
    # ------------------------------------------------------------------

    def append(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Add a new record."""
        with self._lock:
            records = list(self._load())
            records.append(record)
            self._save(records)
        return record

    def update_by_key(
        self, key_field: str, value: str, data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Replace the record where record[key_field] == value."""
        with self._lock:
            records = list(self._load())
            for i, r in enumerate(records):
                if r.get(key_field) == value:
                    records[i] = data
                    self._save(records)
                    return data
        return None

    def delete_by_key(self, key_field: str, value: str) -> bool:
        """Delete the record where record[key_field] == value."""
        with self._lock:
            records = list(self._load())
            new = [r for r in records if r.get(key_field) != value]
            if len(new) == len(records):
                return False
            self._save(new)
        return True

    def replace_all(self, records: List[Dict[str, Any]]) -> None:
        """Replace the entire store contents (used by bulk operations)."""
        with self._lock:
            self._save(records)
