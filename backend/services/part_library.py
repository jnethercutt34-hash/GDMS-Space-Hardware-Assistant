"""Persistent part library — JSON file backed, thread-safe.

Parts are keyed by Part_Number. Re-uploading a datasheet that contains a
part already in the library updates that entry in place.
"""
import json
import os
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List

_LIBRARY_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "library.json")
_lock = threading.Lock()


def _load() -> List[Dict[str, Any]]:
    if not os.path.exists(_LIBRARY_PATH):
        return []
    with open(_LIBRARY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(parts: List[Dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(_LIBRARY_PATH), exist_ok=True)
    with open(_LIBRARY_PATH, "w", encoding="utf-8") as f:
        json.dump(parts, f, indent=2, ensure_ascii=False)


def upsert_parts(new_parts: List[Dict[str, Any]], source_file: str) -> int:
    """Add or update parts from a newly processed datasheet.

    Returns the number of parts that were newly added (not updates).
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    with _lock:
        parts = _load()
        index: Dict[str, int] = {p["Part_Number"]: i for i, p in enumerate(parts)}
        added = 0
        for part in new_parts:
            pn = part.get("Part_Number")
            if not pn:
                continue
            entry = {**part, "source_file": source_file, "added_at": timestamp}
            if pn in index:
                parts[index[pn]] = entry  # update in place
            else:
                parts.append(entry)
                index[pn] = len(parts) - 1
                added += 1
        _save(parts)
    return added


def get_all() -> List[Dict[str, Any]]:
    return _load()


def patch_part(part_number: str, updates: Dict[str, Any]) -> Dict[str, Any] | None:
    """Update specific fields on a part by Part_Number. Returns updated part or None."""
    with _lock:
        parts = _load()
        for i, p in enumerate(parts):
            if p.get("Part_Number") == part_number:
                parts[i] = {**p, **updates}
                _save(parts)
                return parts[i]
    return None


def search(query: str) -> List[Dict[str, Any]]:
    """Case-insensitive substring search across all text fields."""
    q = query.lower().strip()
    if not q:
        return _load()
    results = []
    for part in _load():
        haystack = " ".join(str(v) for v in part.values() if v).lower()
        if q in haystack:
            results.append(part)
    return results
