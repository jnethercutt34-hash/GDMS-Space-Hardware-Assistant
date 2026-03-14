"""One-time migration: JSON files → SQLite.

Imports existing library.json and diagrams.json into the SQLite store.
Safe to run multiple times — skips tables that already have data.

Usage:
    python -m services.migrate          # run standalone
    from services.migrate import run    # import in main.py
"""
import logging
import os

from services.sqlite_store import migrate_json_to_sqlite

logger = logging.getLogger(__name__)

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

_MIGRATIONS = [
    {
        "json_path": os.path.join(_DATA_DIR, "library.json"),
        "table": "parts",
    },
    {
        "json_path": os.path.join(_DATA_DIR, "diagrams.json"),
        "table": "diagrams",
    },
]


def run() -> None:
    """Run all JSON → SQLite migrations."""
    total = 0
    for m in _MIGRATIONS:
        count = migrate_json_to_sqlite(m["json_path"], m["table"])
        total += count
    if total:
        logger.info("Migration complete: %d total records imported.", total)
    else:
        logger.info("Migration check complete: no new records to import.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
