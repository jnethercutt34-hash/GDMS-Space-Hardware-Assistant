"""SQLite-backed record store — drop-in replacement for JsonStore.

Each store maps to a single SQLite table with a JSON blob per row.
Records are stored as individual rows with an `id` (ROWID) and a `data`
column containing the JSON-serialized dict.

The public API is identical to JsonStore:
    get_all(), get_by_key(), append(), update_by_key(),
    delete_by_key(), replace_all()

Internal API used by part_library.py:
    _lock, _load(), _save()

Architecture:
    SqliteStore (this file)
      ├── part_library.py       (parts table — keyed by Part_Number)
      └── block_diagram_store.py (diagrams table — keyed by id)

Migration:
    Use migrate_json_to_sqlite() to import existing JSON files.
"""
import json
import logging
import os
import sqlite3
import threading
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_DB_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
_DB_PATH = os.path.join(_DB_DIR, "store.db")


def _get_db_path() -> str:
    """Return the database path, creating the directory if needed."""
    os.makedirs(_DB_DIR, exist_ok=True)
    return _DB_PATH


class SqliteStore:
    """Thread-safe SQLite record store — drop-in replacement for JsonStore.

    Parameters:
        table: Table name in the SQLite database.
        db_path: Path to the SQLite file (default: data/store.db).
    """

    def __init__(self, table: str, db_path: str | None = None):
        self._table = table
        self._db_path = db_path or _get_db_path()
        self._lock = threading.Lock()
        self._cache: Optional[List[Dict[str, Any]]] = None
        self._init_table()

    def _connect(self) -> sqlite3.Connection:
        """Create a connection with WAL mode for concurrent reads."""
        conn = sqlite3.connect(self._db_path, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_table(self) -> None:
        """Create the table if it doesn't exist."""
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        conn = self._connect()
        try:
            conn.execute(f"""
                CREATE TABLE IF NOT EXISTS [{self._table}] (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    data TEXT NOT NULL
                )
            """)
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Core I/O (internal — matches JsonStore interface)
    # ------------------------------------------------------------------

    def _load(self) -> List[Dict[str, Any]]:
        """Load all records. Uses cache if available."""
        if self._cache is not None:
            return self._cache

        conn = self._connect()
        try:
            rows = conn.execute(
                f"SELECT data FROM [{self._table}] ORDER BY id"
            ).fetchall()
        finally:
            conn.close()

        records = []
        for (data_json,) in rows:
            try:
                records.append(json.loads(data_json))
            except json.JSONDecodeError as exc:
                logger.error("Corrupt row in %s: %s", self._table, exc)
                continue

        self._cache = records
        return self._cache

    def _save(self, records: List[Dict[str, Any]]) -> None:
        """Replace all records (used by part_library bulk operations)."""
        conn = self._connect()
        try:
            conn.execute(f"DELETE FROM [{self._table}]")
            for record in records:
                conn.execute(
                    f"INSERT INTO [{self._table}] (data) VALUES (?)",
                    (json.dumps(record, ensure_ascii=False),),
                )
            conn.commit()
        finally:
            conn.close()
        self._cache = records

    def _invalidate_cache(self) -> None:
        """Force next _load() to read from disk."""
        self._cache = None

    # Compatibility: JsonStore used self._path for test patching.
    # SqliteStore uses self._db_path instead.
    @property
    def _path(self):
        return self._db_path

    @_path.setter
    def _path(self, value):
        self._db_path = value

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
            conn = self._connect()
            try:
                conn.execute(
                    f"INSERT INTO [{self._table}] (data) VALUES (?)",
                    (json.dumps(record, ensure_ascii=False),),
                )
                conn.commit()
            finally:
                conn.close()
            self._cache = None  # invalidate
        return record

    def update_by_key(
        self, key_field: str, value: str, data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Replace the record where record[key_field] == value."""
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    f"SELECT id, data FROM [{self._table}] ORDER BY id"
                ).fetchall()
                for row_id, data_json in rows:
                    record = json.loads(data_json)
                    if record.get(key_field) == value:
                        conn.execute(
                            f"UPDATE [{self._table}] SET data = ? WHERE id = ?",
                            (json.dumps(data, ensure_ascii=False), row_id),
                        )
                        conn.commit()
                        self._cache = None
                        return data
            finally:
                conn.close()
        return None

    def delete_by_key(self, key_field: str, value: str) -> bool:
        """Delete the record where record[key_field] == value."""
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    f"SELECT id, data FROM [{self._table}] ORDER BY id"
                ).fetchall()
                deleted = False
                for row_id, data_json in rows:
                    record = json.loads(data_json)
                    if record.get(key_field) == value:
                        conn.execute(
                            f"DELETE FROM [{self._table}] WHERE id = ?",
                            (row_id,),
                        )
                        deleted = True
                if deleted:
                    conn.commit()
                    self._cache = None
            finally:
                conn.close()
        return deleted

    def replace_all(self, records: List[Dict[str, Any]]) -> None:
        """Replace the entire store contents."""
        with self._lock:
            self._save(records)


# ---------------------------------------------------------------------------
# Migration helper
# ---------------------------------------------------------------------------

def migrate_json_to_sqlite(
    json_path: str,
    table: str,
    db_path: str | None = None,
) -> int:
    """Import records from a JSON file into a SQLite table.

    Returns the number of records migrated. Skips if the table already
    has data (idempotent).
    """
    actual_db = db_path or _get_db_path()
    store = SqliteStore(table, db_path=actual_db)

    # Skip if table already has data
    if store.get_all():
        logger.info(
            "Table '%s' already has %d records — skipping migration.",
            table, len(store.get_all()),
        )
        return 0

    if not os.path.exists(json_path):
        logger.info("JSON file %s not found — nothing to migrate.", json_path)
        return 0

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Failed to read %s for migration: %s", json_path, exc)
        return 0

    if not isinstance(data, list):
        logger.error("Expected JSON array in %s, got %s", json_path, type(data).__name__)
        return 0

    if not data:
        return 0

    store.replace_all(data)
    logger.info(
        "Migrated %d records from %s → table '%s' in %s",
        len(data), json_path, table, actual_db,
    )
    return len(data)
