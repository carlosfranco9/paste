from typing import Optional, List
from dataclasses import dataclass, field
from enum import Enum


class ContentType(Enum):
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    LINK = "link"


@dataclass
class ClipboardData:
    mime_type: str
    raw_data: bytes
    text: Optional[str] = None
    image_data: Optional[bytes] = None
    file_paths: "List[str]" = field(default_factory=list)
    source_app: Optional[str] = None
    window_title: Optional[str] = None

    @property
    def content_type(self) -> ContentType:
        if self.mime_type.startswith("image/"):
            return ContentType.IMAGE
        if self.mime_type == "text/uri-list" and self.file_paths:
            return ContentType.FILE
        if self.text:
            if self.text.strip().startswith(("http://", "https://", "ftp://")):
                return ContentType.LINK
            return ContentType.TEXT
        return ContentType.TEXT

    @property
    def fingerprint_data(self) -> bytes:
        if self.image_data:
            return self.image_data
        if self.text:
            return self.text.encode("utf-8")
        return self.raw_data
