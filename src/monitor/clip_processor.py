import hashlib
import re
import logging
from typing import Optional, Set

from src.monitor.types import ClipboardData, ContentType
from src.storage.file_manager import save_image
from src.database.models import (
    insert_entry, get_entry_by_fingerprint, update_entry_timestamp,
    get_exclusion_rules, ClipboardEntry,
)
from src.utils.dedup import normalize_text
from src.utils.url import is_url_content

logger = logging.getLogger(__name__)


class ClipProcessor:
    def __init__(self):
        self._dedup_cache: Set[str] = set()

    def process(self, data: ClipboardData) -> Optional[ClipboardEntry]:
        if self._is_excluded(data):
            logger.debug("Clip excluded by rules")
            return None

        if data.content_type == ContentType.IMAGE:
            return self._process_image(data)
        return self._process_text(data)

    def _process_text(self, data: ClipboardData) -> Optional[ClipboardEntry]:
        text = (data.text or "").strip()
        if not text:
            return None

        normalized = normalize_text(text)
        fp = hashlib.sha256(normalized.encode()).hexdigest()

        existing = get_entry_by_fingerprint(fp)
        if existing:
            update_entry_timestamp(existing.id)
            return None

        if fp in self._dedup_cache:
            return None
        self._dedup_cache.add(fp)

        entry_type = "link" if is_url_content(text) else "text"
        entry = ClipboardEntry(
            id="",
            type=entry_type,
            content=text,
            plain_text=text,
            fingerprint=fp,
            source_app=data.source_app,
            window_title=data.window_title,
            byte_size=len(data.raw_data),
        )
        entry.id = insert_entry(entry)
        return entry

    def _process_image(self, data: ClipboardData) -> Optional[ClipboardEntry]:
        img_data = data.image_data or data.raw_data
        if not img_data:
            return None

        fp = hashlib.sha256(img_data).hexdigest()

        existing = get_entry_by_fingerprint(fp)
        if existing:
            update_entry_timestamp(existing.id)
            return None

        if fp in self._dedup_cache:
            return None
        self._dedup_cache.add(fp)

        result = save_image(img_data, source_app=data.source_app)
        if result is None:
            return None

        img_uuid, img_path, thumb_path = result
        entry = ClipboardEntry(
            id=img_uuid,
            type="image",
            content=img_path,
            thumbnail_path=thumb_path,
            mime_type=data.mime_type,
            fingerprint=fp,
            source_app=data.source_app,
            window_title=data.window_title,
            byte_size=len(img_data),
        )
        entry.id = insert_entry(entry)
        return entry

    def _is_excluded(self, data: ClipboardData) -> bool:
        rules = get_exclusion_rules(active_only=True)
        app = (data.source_app or "").lower()
        title = (data.window_title or "").lower()
        text = (data.text or "").lower()

        for rule in rules:
            pattern = rule.pattern.lower()
            if rule.rule_type == "app_name":
                if pattern in app:
                    return True
            elif rule.rule_type == "window_title":
                if pattern in title:
                    return True
            elif rule.rule_type == "content_pattern":
                try:
                    if re.search(pattern, text):
                        return True
                except re.error:
                    pass
        return False
