"""Unit tests for SqliteStore — drop-in replacement for JsonStore."""
import json
import os
import threading

import pytest

from services.sqlite_store import SqliteStore, migrate_json_to_sqlite


@pytest.fixture
def store(tmp_path):
    return SqliteStore("test", db_path=os.path.join(str(tmp_path), "test.db"))


class TestBasicCRUD:
    def test_empty_store(self, store):
        assert store.get_all() == []

    def test_append(self, store):
        store.append({"id": "1", "name": "alpha"})
        assert len(store.get_all()) == 1
        assert store.get_all()[0]["name"] == "alpha"

    def test_append_multiple(self, store):
        store.append({"id": "1"})
        store.append({"id": "2"})
        assert len(store.get_all()) == 2

    def test_get_by_key(self, store):
        store.append({"id": "1", "name": "alpha"})
        store.append({"id": "2", "name": "beta"})
        result = store.get_by_key("id", "2")
        assert result is not None
        assert result["name"] == "beta"

    def test_get_by_key_missing(self, store):
        store.append({"id": "1"})
        assert store.get_by_key("id", "999") is None

    def test_update_by_key(self, store):
        store.append({"id": "1", "name": "alpha"})
        result = store.update_by_key("id", "1", {"id": "1", "name": "updated"})
        assert result is not None
        assert result["name"] == "updated"
        assert store.get_by_key("id", "1")["name"] == "updated"

    def test_update_by_key_missing(self, store):
        assert store.update_by_key("id", "999", {"id": "999"}) is None

    def test_delete_by_key(self, store):
        store.append({"id": "1"})
        store.append({"id": "2"})
        assert store.delete_by_key("id", "1") is True
        assert len(store.get_all()) == 1
        assert store.get_by_key("id", "1") is None

    def test_delete_by_key_missing(self, store):
        assert store.delete_by_key("id", "999") is False

    def test_replace_all(self, store):
        store.append({"id": "1"})
        store.replace_all([{"id": "A"}, {"id": "B"}])
        assert len(store.get_all()) == 2
        assert store.get_all()[0]["id"] == "A"


class TestPersistence:
    def test_survives_new_instance(self, tmp_path):
        db_path = os.path.join(str(tmp_path), "test.db")
        store1 = SqliteStore("test", db_path=db_path)
        store1.append({"id": "1", "name": "persisted"})

        store2 = SqliteStore("test", db_path=db_path)
        assert len(store2.get_all()) == 1
        assert store2.get_all()[0]["name"] == "persisted"

    def test_creates_directory(self, tmp_path):
        db_path = os.path.join(str(tmp_path), "a", "b", "test.db")
        store = SqliteStore("test", db_path=db_path)
        store.append({"id": "1"})
        assert os.path.exists(db_path)


class TestCaching:
    def test_cache_populated_after_read(self, store):
        store.append({"id": "1"})
        store._cache = None  # clear cache
        store.get_all()
        assert store._cache is not None

    def test_cache_invalidated_after_append(self, store):
        store.append({"id": "1"})
        store.get_all()  # populate cache
        store.append({"id": "2"})
        # Cache should be invalidated (None) — next get_all reads from DB
        assert store._cache is None

    def test_save_updates_cache(self, store):
        store._save([{"id": "1"}])
        assert store._cache is not None
        assert len(store._cache) == 1


class TestInternalAPI:
    """Test _load, _save, _lock — used directly by part_library.py."""

    def test_load_returns_list(self, store):
        store.append({"id": "1"})
        store._cache = None
        records = store._load()
        assert isinstance(records, list)
        assert len(records) == 1

    def test_save_replaces_all(self, store):
        store.append({"id": "1"})
        store._save([{"id": "A"}, {"id": "B"}])
        assert len(store.get_all()) == 2

    def test_lock_exists(self, store):
        assert hasattr(store, "_lock")
        assert isinstance(store._lock, type(threading.Lock()))

    def test_path_property(self, store):
        assert store._path == store._db_path


class TestMultipleTables:
    def test_separate_tables(self, tmp_path):
        db_path = os.path.join(str(tmp_path), "shared.db")
        parts = SqliteStore("parts", db_path=db_path)
        diagrams = SqliteStore("diagrams", db_path=db_path)

        parts.append({"Part_Number": "TPS7H1111"})
        diagrams.append({"id": "diag_01", "name": "Board"})

        assert len(parts.get_all()) == 1
        assert len(diagrams.get_all()) == 1
        assert parts.get_all()[0]["Part_Number"] == "TPS7H1111"
        assert diagrams.get_all()[0]["name"] == "Board"


class TestThreadSafety:
    def test_concurrent_appends(self, tmp_path):
        db_path = os.path.join(str(tmp_path), "concurrent.db")
        store = SqliteStore("test", db_path=db_path)
        errors = []

        def append_records(start):
            try:
                for i in range(20):
                    store.append({"id": str(start + i)})
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=append_records, args=(i * 20,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        assert len(store.get_all()) == 100


class TestMigration:
    def test_migrate_json_to_sqlite(self, tmp_path):
        # Create a JSON file
        json_path = os.path.join(str(tmp_path), "data.json")
        records = [{"id": "1", "name": "alpha"}, {"id": "2", "name": "beta"}]
        with open(json_path, "w") as f:
            json.dump(records, f)

        db_path = os.path.join(str(tmp_path), "migrate.db")
        count = migrate_json_to_sqlite(json_path, "test", db_path=db_path)
        assert count == 2

        store = SqliteStore("test", db_path=db_path)
        assert len(store.get_all()) == 2

    def test_migrate_idempotent(self, tmp_path):
        json_path = os.path.join(str(tmp_path), "data.json")
        with open(json_path, "w") as f:
            json.dump([{"id": "1"}], f)

        db_path = os.path.join(str(tmp_path), "migrate.db")
        count1 = migrate_json_to_sqlite(json_path, "test", db_path=db_path)
        count2 = migrate_json_to_sqlite(json_path, "test", db_path=db_path)
        assert count1 == 1
        assert count2 == 0  # skipped — already has data

    def test_migrate_missing_file(self, tmp_path):
        db_path = os.path.join(str(tmp_path), "migrate.db")
        count = migrate_json_to_sqlite("/nonexistent.json", "test", db_path=db_path)
        assert count == 0

    def test_migrate_corrupt_json(self, tmp_path):
        json_path = os.path.join(str(tmp_path), "corrupt.json")
        with open(json_path, "w") as f:
            f.write("{broken!!")

        db_path = os.path.join(str(tmp_path), "migrate.db")
        count = migrate_json_to_sqlite(json_path, "test", db_path=db_path)
        assert count == 0
