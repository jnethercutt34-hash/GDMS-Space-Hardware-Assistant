"""Persistent block diagram store — SQLite backed, thread-safe.

Thin wrapper around SqliteStore. Diagrams are keyed by 'id'.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from services.sqlite_store import SqliteStore

_store = SqliteStore("diagrams")


def list_all() -> List[Dict[str, Any]]:
    return _store.get_all()


def get_by_id(diagram_id: str) -> Optional[Dict[str, Any]]:
    return _store.get_by_key("id", diagram_id)


def create(diagram: Dict[str, Any]) -> Dict[str, Any]:
    return _store.append(diagram)


def update(diagram_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    data["id"] = diagram_id
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    # Preserve created_at from existing record
    existing = get_by_id(diagram_id)
    if existing:
        data.setdefault("created_at", existing.get("created_at"))
        return _store.update_by_key("id", diagram_id, data)
    return None


def delete(diagram_id: str) -> bool:
    return _store.delete_by_key("id", diagram_id)
