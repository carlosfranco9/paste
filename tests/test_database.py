import os
import sys
import tempfile
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ["PASTE_DEBUG"] = "1"
os.environ["XDG_SESSION_TYPE"] = "x11"

import pytest
from src.database.db import DatabaseManager, DATA_DIR, DB_PATH
from src.database.models import (
    insert_entry, get_entry_by_fingerprint, get_recent_entries,
    toggle_pin, delete_entry, clear_entries, ClipboardEntry,
)
from src.database.search import count_entries, search_entries


@pytest.fixture(autouse=True)
def temp_db():
    with tempfile.TemporaryDirectory() as tmp:
        old_data = str(DATA_DIR)
        DATA_DIR_ATTR = "src.database.db.DATA_DIR"
        # Override DATA_DIR for testing
        import src.database.db as db_module
        original = db_module.DATA_DIR
        db_module.DATA_DIR = Path(tmp)
        db_module.DB_PATH = db_module.DATA_DIR / "paste.db"

        db_module.DatabaseManager._instance = None
        db = DatabaseManager()

        yield db

        db.close()
        db_module.DATA_DIR = original


@pytest.fixture
def sample_entry():
    return ClipboardEntry(
        id=uuid.uuid4().hex,
        type="text",
        content="Hello World",
        plain_text="Hello World",
        fingerprint="",
        byte_size=11,
    )


class TestDatabase:
    def test_insert_and_find(self, sample_entry):
        eid = insert_entry(sample_entry)
        assert eid == sample_entry.id

        found = get_entry_by_fingerprint("")
        assert found is not None
        assert found.id == eid

    def test_get_recent_entries(self, sample_entry):
        insert_entry(sample_entry)
        entries = get_recent_entries(limit=10)
        assert len(entries) >= 1
        assert entries[0].id == sample_entry.id

    def test_toggle_pin(self, sample_entry):
        insert_entry(sample_entry)
        result = toggle_pin(sample_entry.id)
        assert result is True

        entries = get_recent_entries(pinned_only=True)
        assert len(entries) == 1

    def test_soft_delete(self, sample_entry):
        insert_entry(sample_entry)
        delete_entry(sample_entry.id, hard=False)

        entries = get_recent_entries()
        assert len(entries) == 0

    def test_hard_delete(self, sample_entry):
        insert_entry(sample_entry)
        delete_entry(sample_entry.id, hard=True)

        entries = get_recent_entries()
        assert len(entries) == 0

    def test_clear_entries(self, sample_entry):
        insert_entry(sample_entry)
        second = ClipboardEntry(
            id=uuid.uuid4().hex,
            type="link",
            content="https://example.com",
            fingerprint="second",
        )
        insert_entry(second)

        assert clear_entries() == 2
        assert get_recent_entries() == []

    def test_url_filter_includes_legacy_text_entries_containing_address(self):
        url_text = ClipboardEntry(
            id=uuid.uuid4().hex,
            type="text",
            content="Documentation: https://docs.example.com/guide",
            plain_text="Documentation: https://docs.example.com/guide",
            fingerprint="legacy-url-text",
        )
        normal_text = ClipboardEntry(
            id=uuid.uuid4().hex,
            type="text",
            content="Documentation without an address",
            plain_text="Documentation without an address",
            fingerprint="normal-text",
        )
        insert_entry(url_text)
        insert_entry(normal_text)

        filtered = get_recent_entries(entry_type="link")
        searched = search_entries("docs.example", entry_type="link")

        assert [entry.id for entry in filtered] == [url_text.id]
        assert [row[0] for row in searched] == [url_text.id]
        assert count_entries("link") == 1
