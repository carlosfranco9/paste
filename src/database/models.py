import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal, Optional, List

from src.database.db import DatabaseManager

EntryType = Literal["text", "image", "file", "link"]

URL_FILTER_CONDITION = """(
    e.type='link'
    OR paste_contains_url(e.content)=1
    OR paste_contains_url(COALESCE(e.plain_text, ''))=1
)"""


@dataclass
class ClipboardEntry:
    id: str
    type: EntryType
    content: str
    plain_text: Optional[str] = None
    mime_type: Optional[str] = None
    thumbnail_path: Optional[str] = None
    source_app: Optional[str] = None
    window_title: Optional[str] = None
    fingerprint: str = ""
    pinned: bool = False
    pinboard_id: Optional[str] = None
    byte_size: int = 0
    created_at: str = ""
    updated_at: str = ""
    is_deleted: bool = False

    @classmethod
    def from_row(cls, row: tuple) -> "ClipboardEntry":
        return cls(
            id=row[0], type=row[1], content=row[2],
            plain_text=row[3], mime_type=row[4],
            thumbnail_path=row[5], source_app=row[6],
            window_title=row[7], fingerprint=row[8],
            pinned=bool(row[9]), pinboard_id=row[10],
            byte_size=row[11] or 0, created_at=row[12],
            updated_at=row[13] or "", is_deleted=bool(row[14]),
        )


def insert_entry(entry: ClipboardEntry) -> str:
    db = DatabaseManager()
    now = datetime.now(timezone.utc).isoformat()
    entry_id = entry.id or uuid.uuid4().hex
    db.execute(
        """INSERT INTO entries
           (id, type, content, plain_text, mime_type, thumbnail_path,
            source_app, window_title, fingerprint, pinned, pinboard_id,
            byte_size, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (entry_id, entry.type, entry.content, entry.plain_text,
         entry.mime_type, entry.thumbnail_path, entry.source_app,
         entry.window_title, entry.fingerprint,
         1 if entry.pinned else 0, entry.pinboard_id,
         entry.byte_size, now, now),
    )
    db.commit()
    return entry_id


def update_entry_timestamp(entry_id: str):
    db = DatabaseManager()
    now = datetime.now(timezone.utc).isoformat()
    db.execute(
        "UPDATE entries SET updated_at=? WHERE id=?",
        (now, entry_id),
    )
    db.commit()


def get_entry_by_id(entry_id: str):
    db = DatabaseManager()
    return db.fetchone(
        "SELECT * FROM entries WHERE id=? AND is_deleted=0",
        (entry_id,),
    )


def get_entry_by_fingerprint(fingerprint: str) -> Optional[ClipboardEntry]:
    db = DatabaseManager()
    row = db.fetchone(
        "SELECT * FROM entries WHERE fingerprint=? AND is_deleted=0",
        (fingerprint,),
    )
    return ClipboardEntry.from_row(row) if row else None


def get_recent_entries(
    limit: int = 50,
    offset: int = 0,
    entry_type: Optional[str] = None,
    pinned_only: bool = False,
    pinboard_id: Optional[str] = None,
    search_query: Optional[str] = None,
    ) -> List[ClipboardEntry]:
    db = DatabaseManager()
    conditions = ["e.is_deleted=0"]
    params: list = []

    if entry_type:
        if entry_type == "link":
            conditions.append(URL_FILTER_CONDITION)
        else:
            conditions.append("e.type=?")
            params.append(entry_type)
    if pinned_only:
        conditions.append("e.pinned=1")
    if pinboard_id:
        conditions.append("e.pinboard_id=?")
        params.append(pinboard_id)

    if search_query:
        conditions.append(
            "e.rowid IN (SELECT rowid FROM entries_fts WHERE entries_fts MATCH ?)"
        )
        params.append(search_query)

    where = " AND ".join(conditions)
    sql = f"SELECT e.* FROM entries e WHERE {where} ORDER BY e.updated_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    rows = db.fetchall(sql, params)
    return [ClipboardEntry.from_row(r) for r in rows]


def toggle_pin(entry_id: str) -> bool:
    db = DatabaseManager()
    entry = db.fetchone(
        "SELECT pinned FROM entries WHERE id=?", (entry_id,)
    )
    if not entry:
        return False
    new_val = 0 if entry[0] else 1
    db.execute("UPDATE entries SET pinned=? WHERE id=?", (new_val, entry_id))
    db.commit()
    return bool(new_val)


def set_pinboard(entry_id: str, pinboard_id: Optional[str]):
    db = DatabaseManager()
    db.execute(
        "UPDATE entries SET pinboard_id=? WHERE id=?",
        (pinboard_id, entry_id),
    )
    db.commit()


def dedup_entries():
    db = DatabaseManager()
    rows = db.fetchall(
        """SELECT id, fingerprint, created_at FROM entries
           WHERE is_deleted=0 ORDER BY created_at DESC"""
    )
    seen = {}
    for row in rows:
        eid, fp, created = row
        if fp in seen:
            db.execute("UPDATE entries SET is_deleted=1 WHERE id=?", (eid,))
        else:
            seen[fp] = eid
    db.commit()


def delete_entry(entry_id: str, hard: bool = False):
    db = DatabaseManager()
    if hard:
        cursor = db.execute("DELETE FROM entries WHERE id=?", (entry_id,))
    else:
        cursor = db.execute(
            "UPDATE entries SET is_deleted=1 WHERE id=? AND is_deleted=0",
            (entry_id,),
        )
    db.commit()
    return cursor.rowcount > 0


def clear_entries() -> int:
    db = DatabaseManager()
    cursor = db.execute(
        "UPDATE entries SET is_deleted=1 WHERE is_deleted=0"
    )
    db.commit()
    return cursor.rowcount


# --- Pinboard operations ---

@dataclass
class Pinboard:
    id: str
    name: str
    icon: str = "folder"
    sort_order: int = 0
    created_at: str = ""

    @classmethod
    def from_row(cls, row: tuple) -> "Pinboard":
        return cls(id=row[0], name=row[1], icon=row[2] or "folder",
                   sort_order=row[3] or 0, created_at=row[4])


def create_pinboard(name: str, icon: str = "folder") -> str:
    db = DatabaseManager()
    now = datetime.now(timezone.utc).isoformat()
    pid = uuid.uuid4().hex
    db.execute(
        "INSERT INTO pinboards (id, name, icon, sort_order, created_at) VALUES (?,?,?,?,?)",
        (pid, name, icon, 0, now),
    )
    db.commit()
    return pid


def get_pinboards() -> List[Pinboard]:
    db = DatabaseManager()
    rows = db.fetchall(
        "SELECT * FROM pinboards ORDER BY sort_order ASC, created_at ASC"
    )
    return [Pinboard.from_row(r) for r in rows]


def delete_pinboard(pinboard_id: str):
    db = DatabaseManager()
    db.execute("DELETE FROM pinboards WHERE id=?", (pinboard_id,))
    db.commit()


# --- Exclusion rules ---

@dataclass
class ExclusionRule:
    id: int
    rule_type: str
    pattern: str
    is_active: bool
    created_at: str


def add_exclusion_rule(rule_type: str, pattern: str) -> int:
    db = DatabaseManager()
    now = datetime.now(timezone.utc).isoformat()
    cursor = db.execute(
        "INSERT INTO exclusion_rules (rule_type, pattern, created_at) VALUES (?,?,?)",
        (rule_type, pattern, now),
    )
    db.commit()
    return cursor.lastrowid


def get_exclusion_rules(active_only: bool = True) -> List[ExclusionRule]:
    db = DatabaseManager()
    if active_only:
        rows = db.fetchall(
            "SELECT * FROM exclusion_rules WHERE is_active=1 ORDER BY id"
        )
    else:
        rows = db.fetchall(
            "SELECT * FROM exclusion_rules ORDER BY id"
        )
    return [
        ExclusionRule(id=r[0], rule_type=r[1], pattern=r[2],
                      is_active=bool(r[3]), created_at=r[4])
        for r in rows
    ]


def delete_exclusion_rule(rule_id: int):
    db = DatabaseManager()
    db.execute("DELETE FROM exclusion_rules WHERE id=?", (rule_id,))
    db.commit()
