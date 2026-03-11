"""Persistent block diagram store — JSON file backed, thread-safe."""
import json
import os
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

_STORE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "diagrams.json")
_lock = threading.Lock()


def _load() -> List[Dict[str, Any]]:
    if not os.path.exists(_STORE_PATH):
        return []
    with open(_STORE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(diagrams: List[Dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(_STORE_PATH), exist_ok=True)
    with open(_STORE_PATH, "w", encoding="utf-8") as f:
        json.dump(diagrams, f, indent=2, ensure_ascii=False)


def list_all() -> List[Dict[str, Any]]:
    return _load()


def get_by_id(diagram_id: str) -> Optional[Dict[str, Any]]:
    for d in _load():
        if d.get("id") == diagram_id:
            return d
    return None


def create(diagram: Dict[str, Any]) -> Dict[str, Any]:
    with _lock:
        diagrams = _load()
        diagrams.append(diagram)
        _save(diagrams)
    return diagram


def update(diagram_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    with _lock:
        diagrams = _load()
        for i, d in enumerate(diagrams):
            if d.get("id") == diagram_id:
                data["id"] = diagram_id
                data["updated_at"] = datetime.now(timezone.utc).isoformat()
                # Preserve created_at
                data.setdefault("created_at", d.get("created_at"))
                diagrams[i] = data
                _save(diagrams)
                return data
    return None


def delete(diagram_id: str) -> bool:
    with _lock:
        diagrams = _load()
        new = [d for d in diagrams if d.get("id") != diagram_id]
        if len(new) == len(diagrams):
            return False
        _save(new)
    return True
