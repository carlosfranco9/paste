import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
import os
import tempfile

os.environ["PASTE_DEBUG"] = "1"
os.environ["XDG_SESSION_TYPE"] = "x11"

from src.database.db import DatabaseManager, DATA_DIR
from src.monitor.clip_processor import ClipProcessor
from src.monitor.types import ClipboardData
from src.database.models import add_exclusion_rule


@pytest.fixture(autouse=True)
def temp_db():
    with tempfile.TemporaryDirectory() as tmp:
        import src.database.db as db_module
        original = db_module.DATA_DIR
        db_module.DATA_DIR = Path(tmp)
        db_module.DB_PATH = db_module.DATA_DIR / "paste.db"
        db_module.DatabaseManager._instance = None
        db = DatabaseManager()
        yield db
        db.close()
        db_module.DATA_DIR = original


class TestClipProcessor:
    def setup_method(self):
        self.processor = ClipProcessor()

    def test_process_text(self):
        data = ClipboardData(
            mime_type="text/plain",
            raw_data=b"hello world",
            text="hello world",
        )
        entry = self.processor.process(data)
        assert entry is not None
        assert entry.type == "text"
        assert entry.content == "hello world"

    def test_process_empty_text_returns_none(self):
        data = ClipboardData(
            mime_type="text/plain",
            raw_data=b"",
            text="",
        )
        entry = self.processor.process(data)
        assert entry is None

    def test_process_link(self):
        data = ClipboardData(
            mime_type="text/plain",
            raw_data=b"https://example.com",
            text="https://example.com",
        )
        entry = self.processor.process(data)
        assert entry is not None
        assert entry.type == "link"

    @pytest.mark.parametrize(
        "value",
        ["ftp://example.com/file", "www.example.com/path", "example.cn/docs"],
    )
    def test_process_additional_url_formats(self, value):
        data = ClipboardData(
            mime_type="text/plain",
            raw_data=value.encode(),
            text=value,
        )

        entry = self.processor.process(data)

        assert entry is not None
        assert entry.type == "link"

    def test_text_containing_url_remains_text_for_safe_preview(self):
        value = "See https://example.com for details"
        data = ClipboardData(
            mime_type="text/plain",
            raw_data=value.encode(),
            text=value,
        )

        entry = self.processor.process(data)

        assert entry is not None
        assert entry.type == "text"

    def test_dedup_same_content_returns_none(self):
        data1 = ClipboardData(
            mime_type="text/plain",
            raw_data=b"test",
            text="test",
        )
        data2 = ClipboardData(
            mime_type="text/plain",
            raw_data=b"test",
            text="test",
        )
        e1 = self.processor.process(data1)
        e2 = self.processor.process(data2)
        assert e1 is not None
        assert e2 is None

    def test_exclusion_by_app_name(self):
        add_exclusion_rule("app_name", "gedit")
        data = ClipboardData(
            mime_type="text/plain",
            raw_data=b"secret",
            text="secret",
            source_app="gedit",
        )
        entry = self.processor.process(data)
        assert entry is None

    def test_exclusion_by_content_pattern(self):
        add_exclusion_rule("content_pattern", "^password")
        data = ClipboardData(
            mime_type="text/plain",
            raw_data=b"password=123",
            text="password=123",
        )
        entry = self.processor.process(data)
        assert entry is None
