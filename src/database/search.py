import re
from typing import Optional, List

from src.database.db import DatabaseManager
from src.database.models import URL_FILTER_CONDITION


def search_entries(
    query: str,
    limit: int = 50,
    offset: int = 0,
    entry_type: Optional[str] = None,
) -> List[tuple]:
    db = DatabaseManager()
    if not query.strip():
        return []

    conditions: List[str] = ["e.is_deleted=0"]
    params: List[str] = []

    like_pattern = f"%{query}%"
    conditions.append("(e.content LIKE ? OR e.plain_text LIKE ?)")
    params.extend([like_pattern, like_pattern])

    if entry_type:
        if entry_type == "link":
            conditions.append(URL_FILTER_CONDITION)
        else:
            conditions.append("e.type=?")
            params.append(entry_type)

    where = " AND ".join(conditions)
    sql = f"SELECT e.* FROM entries e WHERE {where} ORDER BY e.updated_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    return db.fetchall(sql, params)


def fts_search(
    query: str,
    limit: int = 50,
    offset: int = 0,
    entry_type: Optional[str] = None,
) -> List[tuple]:
    return search_entries(query, limit, offset, entry_type)


def count_entries(entry_type: Optional[str] = None) -> int:
    db = DatabaseManager()
    if entry_type:
        if entry_type == "link":
            row = db.fetchone(
                f"SELECT COUNT(*) FROM entries e "
                f"WHERE e.is_deleted=0 AND {URL_FILTER_CONDITION}"
            )
        else:
            row = db.fetchone(
                "SELECT COUNT(*) FROM entries e "
                "WHERE e.type=? AND e.is_deleted=0",
                (entry_type,),
            )
    else:
        row = db.fetchone(
            "SELECT COUNT(*) FROM entries WHERE is_deleted=0"
        )
    return row[0] if row else 0


def get_total_size() -> int:
    db = DatabaseManager()
    row = db.fetchone("SELECT COALESCE(SUM(byte_size), 0) FROM entries WHERE is_deleted=0")
    return row[0] if row else 0
