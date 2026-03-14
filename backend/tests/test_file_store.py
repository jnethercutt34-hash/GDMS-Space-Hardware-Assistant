"""Unit tests for FileStore base class."""
import os

import pytest

from services.file_store import FileStore


class TestSanitize:
    def test_basic_filename(self, tmp_path):
        store = FileStore(str(tmp_path), ".pdf", binary=True)
        assert store.sanitize("datasheet.pdf") == "datasheet.pdf"

    def test_strips_path_components(self, tmp_path):
        store = FileStore(str(tmp_path), ".pdf", binary=True)
        # os.path.basename extracts just the last component
        assert store.sanitize("../../etc/passwd.pdf") == "passwd.pdf"

    def test_adds_extension(self, tmp_path):
        store = FileStore(str(tmp_path), ".pdf", binary=True)
        assert store.sanitize("datasheet") == "datasheet.pdf"

    def test_keeps_matching_extension_case(self, tmp_path):
        # .PDF matches .pdf (case-insensitive), so it's kept as-is
        store = FileStore(str(tmp_path), ".pdf", binary=True)
        result = store.sanitize("datasheet.PDF")
        assert result == "datasheet.PDF"

    def test_replaces_wrong_extension(self, tmp_path):
        store = FileStore(str(tmp_path), ".txt", binary=False)
        assert store.sanitize("datasheet.pdf") == "datasheet.txt"

    def test_empty_becomes_unnamed(self, tmp_path):
        store = FileStore(str(tmp_path), ".pdf", binary=True)
        result = store.sanitize("")
        assert result.endswith(".pdf")

    def test_special_characters_stripped(self, tmp_path):
        store = FileStore(str(tmp_path), ".pdf", binary=True)
        result = store.sanitize("data sheet (v2) [final].pdf")
        assert "/" not in result
        assert "\\" not in result


class TestSave:
    def test_save_returns_filename(self, tmp_path):
        store = FileStore(str(tmp_path), ".pdf", binary=True)
        name = store.save(b"fake pdf content", "test.pdf")
        assert name.endswith(".pdf")
        assert os.path.exists(os.path.join(str(tmp_path), name))

    def test_save_binary(self, tmp_path):
        store = FileStore(str(tmp_path), ".pdf", binary=True)
        content = b"\x00\x01\x02\x03"
        name = store.save(content, "binary.pdf")
        with open(os.path.join(str(tmp_path), name), "rb") as f:
            assert f.read() == content

    def test_save_text(self, tmp_path):
        store = FileStore(str(tmp_path), ".txt", binary=False)
        content = "Hello, world!"
        name = store.save(content, "hello.txt")
        with open(os.path.join(str(tmp_path), name), "r", encoding="utf-8") as f:
            assert f.read() == content

    def test_dedup_same_name_same_content(self, tmp_path):
        """Same filename + same content → returns same filename, no duplicate."""
        store = FileStore(str(tmp_path), ".pdf", binary=True)
        name1 = store.save(b"same content", "file.pdf")
        name2 = store.save(b"same content", "file.pdf")
        assert name1 == name2
        files = os.listdir(str(tmp_path))
        assert len(files) == 1

    def test_collision_different_content_same_name(self, tmp_path):
        """Same filename + different content → hash suffix added."""
        store = FileStore(str(tmp_path), ".pdf", binary=True)
        name1 = store.save(b"content A", "file.pdf")
        name2 = store.save(b"content B", "file.pdf")
        assert name1 != name2
        assert "_" in name2  # hash suffix added

    def test_different_content_different_files(self, tmp_path):
        store = FileStore(str(tmp_path), ".pdf", binary=True)
        name1 = store.save(b"content A", "file1.pdf")
        name2 = store.save(b"content B", "file2.pdf")
        assert name1 != name2

    def test_first_save_keeps_original_name(self, tmp_path):
        store = FileStore(str(tmp_path), ".pdf", binary=True)
        name = store.save(b"test content", "original.pdf")
        # First save keeps original name (no hash suffix)
        assert name == "original.pdf"


class TestGetPath:
    def test_get_path(self, tmp_path):
        store = FileStore(str(tmp_path), ".pdf", binary=True)
        name = store.save(b"content", "test.pdf")
        path = store.get_path(name)
        assert os.path.isabs(path)
        assert os.path.exists(path)

    def test_get_path_nonexistent(self, tmp_path):
        store = FileStore(str(tmp_path), ".pdf", binary=True)
        path = store.get_path("nonexistent.pdf")
        assert path is None


class TestExists:
    def test_exists_true(self, tmp_path):
        store = FileStore(str(tmp_path), ".pdf", binary=True)
        name = store.save(b"content", "test.pdf")
        assert store.exists(name) is True

    def test_exists_false(self, tmp_path):
        store = FileStore(str(tmp_path), ".pdf", binary=True)
        assert store.exists("nonexistent.pdf") is False


class TestCreatesDirOnSave:
    def test_creates_missing_directory(self, tmp_path):
        nested = os.path.join(str(tmp_path), "a", "b", "c")
        store = FileStore(nested, ".pdf", binary=True)
        name = store.save(b"content", "test.pdf")
        assert os.path.exists(os.path.join(nested, name))
