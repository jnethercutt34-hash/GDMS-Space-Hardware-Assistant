"""Unit tests for JsonStore base class."""
import json
import os
import threading

import pytest

from services.json_store import JsonStore


@pytest.fixture
def store(tmp_path):
    return JsonStore(os.path.join(str(tmp_path), "test.json"))


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
        path = os.path.join(str(tmp_path), "test.json")
        store1 = JsonStore(path)
        store1.append({"id": "1", "name": "persisted"})

        store2 = JsonStore(path)
        assert len(store2.get_all()) == 1
        assert store2.get_all()[0]["name"] == "persisted"

    def test_creates_directory(self, tmp_path):
        path = os.path.join(str(tmp_path), "a", "b", "test.json")
        store = JsonStore(path)
        store.append({"id": "1"})
        assert os.path.exists(path)


class TestCaching:
    def test_cache_populated_after_read(self, store):
        store.append({"id": "1"})
        # Read populates cache
        store.get_all()
        assert store._cache is not None

    def test_cache_invalidated_after_write(self, store):
        store.append({"id": "1"})
        store.get_all()  # populate cache
        # Direct _invalidate_cache clears it
        store._invalidate_cache()
        assert store._cache is None

    def test_save_updates_cache(self, store):
        store.append({"id": "1"})
        # After append, cache should reflect the new data
        assert store._cache is not None
        assert len(store._cache) == 1


class TestCorruptionHandling:
    def test_corrupt_json_returns_empty(self, tmp_path):
        path = os.path.join(str(tmp_path), "corrupt.json")
        with open(path, "w") as f:
            f.write("{broken json!!")
        store = JsonStore(path)
        assert store.get_all() == []

    def test_non_array_json_returns_empty(self, tmp_path):
        path = os.path.join(str(tmp_path), "object.json")
        with open(path, "w") as f:
            json.dump({"not": "an array"}, f)
        store = JsonStore(path)
        assert store.get_all() == []

    def test_missing_file_returns_empty(self, tmp_path):
        path = os.path.join(str(tmp_path), "missing.json")
        store = JsonStore(path)
        assert store.get_all() == []


class TestThreadSafety:
    def test_concurrent_appends(self, tmp_path):
        path = os.path.join(str(tmp_path), "concurrent.json")
        store = JsonStore(path)
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
