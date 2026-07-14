import os
import sqlite3
import threading
from pathlib import Path

DATA_DIR = Path.home() / ".paste"
DB_PATH = DATA_DIR / "paste.db"


class DatabaseManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance

    def _init(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.execute("PRAGMA busy_timeout=5000")
        self.write_lock = threading.Lock()
        self._init_schema()

    def _init_schema(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS entries (
                id            TEXT PRIMARY KEY,
                type          TEXT NOT NULL CHECK(type IN ('text','image','file','link')),
                content       TEXT NOT NULL,
                plain_text    TEXT,
                mime_type     TEXT,
                thumbnail_path TEXT,
                source_app    TEXT,
                window_title  TEXT,
                fingerprint   TEXT NOT NULL,
                pinned        INTEGER NOT NULL DEFAULT 0,
                pinboard_id   TEXT REFERENCES pinboards(id) ON DELETE SET NULL,
                byte_size     INTEGER,
                created_at    TEXT NOT NULL,
                updated_at    TEXT NOT NULL DEFAULT '',
                is_deleted    INTEGER NOT NULL DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_entries_created
                ON entries(created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_entries_type
                ON entries(type);
            CREATE INDEX IF NOT EXISTS idx_entries_pinned
                ON entries(pinned);
            CREATE INDEX IF NOT EXISTS idx_entries_fingerprint
                ON entries(fingerprint);

            CREATE TABLE IF NOT EXISTS pinboards (
                id          TEXT PRIMARY KEY,
                name        TEXT NOT NULL,
                icon        TEXT DEFAULT 'folder',
                sort_order  INTEGER NOT NULL DEFAULT 0,
                created_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS exclusion_rules (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_type   TEXT NOT NULL CHECK(rule_type IN ('app_name','window_title','content_pattern')),
                pattern     TEXT NOT NULL,
                is_active   INTEGER NOT NULL DEFAULT 1,
                created_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS config (
                key   TEXT PRIMARY KEY,
                value TEXT
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS entries_fts USING fts5(
                content, plain_text, source_app,
                content='entries',
                content_rowid='rowid'
            );

            CREATE TRIGGER IF NOT EXISTS entries_ai AFTER INSERT ON entries BEGIN
                INSERT INTO entries_fts(rowid, content, plain_text, source_app)
                VALUES (new.rowid, new.content, new.plain_text, new.source_app);
            END;

            CREATE TRIGGER IF NOT EXISTS entries_ad AFTER DELETE ON entries BEGIN
                INSERT INTO entries_fts(entries_fts, rowid, content, plain_text, source_app)
                VALUES ('delete', old.rowid, old.content, old.plain_text, old.source_app);
            END;

            CREATE TRIGGER IF NOT EXISTS entries_au AFTER UPDATE ON entries BEGIN
                INSERT INTO entries_fts(entries_fts, rowid, content, plain_text, source_app)
                VALUES ('delete', old.rowid, old.content, old.plain_text, old.source_app);
                INSERT INTO entries_fts(rowid, content, plain_text, source_app)
                VALUES (new.rowid, new.content, new.plain_text, new.source_app);
            END;
        """)
        self.conn.commit()

    def execute(self, sql, params=()):
        with self.write_lock:
            return self.conn.execute(sql, params)

    def executemany(self, sql, params_list):
        with self.write_lock:
            return self.conn.executemany(sql, params_list)

    def fetchall(self, sql, params=()):
        return self.conn.execute(sql, params).fetchall()

    def fetchone(self, sql, params=()):
        return self.conn.execute(sql, params).fetchone()

    def commit(self):
        with self.write_lock:
            self.conn.commit()

    def close(self):
        self.conn.close()
        DatabaseManager._instance = None
