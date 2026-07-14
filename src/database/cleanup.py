import os
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path

from src.database.db import DatabaseManager
from src.database.models import get_recent_entries

DATA_DIR = Path.home() / ".paste"
MEDIA_DIR = DATA_DIR / "media"


def cleanup_expired(max_days: int = 30):
    db = DatabaseManager()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=max_days)).isoformat()

    rows = db.fetchall(
        """SELECT id, thumbnail_path FROM entries
           WHERE is_deleted=0 AND pinned=0
           AND updated_at < ?""",
        (cutoff,),
    )

    for row in rows:
        entry_id, thumb_path = row
        if thumb_path:
            _remove_file(thumb_path)
        db.execute("UPDATE entries SET is_deleted=1 WHERE id=?", (entry_id,))

    db.commit()
    return len(rows)


def cleanup_overflow(max_entries: int = 1000):
    db = DatabaseManager()
    row = db.fetchone(
        "SELECT COUNT(*) FROM entries WHERE is_deleted=0 AND pinned=0"
    )
    if not row or row[0] <= max_entries:
        return 0

    excess = row[0] - max_entries
    old_entries = db.fetchall(
        """SELECT id, thumbnail_path FROM entries
           WHERE is_deleted=0 AND pinned=0
           ORDER BY updated_at ASC LIMIT ?""",
        (excess,),
    )
    for entry_id, thumb_path in old_entries:
        if thumb_path:
            _remove_file(thumb_path)
        db.execute("UPDATE entries SET is_deleted=1 WHERE id=?", (entry_id,))

    db.commit()
    return excess


def cleanup_media_limit(max_mb: int = 2000):
    db = DatabaseManager()
    row = db.fetchone(
        "SELECT COALESCE(SUM(byte_size), 0) FROM entries WHERE is_deleted=0 AND pinned=0 AND type='image'"
    )
    total_bytes = row[0] if row else 0
    if total_bytes <= max_mb * 1024 * 1024:
        return 0

    excess_bytes = total_bytes - max_mb * 1024 * 1024
    freed = 0
    rows = db.fetchall(
        """SELECT id, thumbnail_path, byte_size FROM entries
           WHERE is_deleted=0 AND pinned=0 AND type='image'
           ORDER BY updated_at ASC"""
    )
    for entry_id, thumb_path, byte_size in rows:
        if freed >= excess_bytes:
            break
        if thumb_path:
            _remove_file(thumb_path)
        db.execute("UPDATE entries SET is_deleted=1 WHERE id=?", (entry_id,))
        freed += byte_size or 0

    db.commit()
    return len(rows)


def vacuum():
    db = DatabaseManager()
    db.execute("VACUUM")
    db.commit()


def _remove_file(path: str):
    full_path = Path(path)
    if full_path.exists():
        full_path.unlink(missing_ok=True)
