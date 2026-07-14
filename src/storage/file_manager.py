import io
import uuid
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image

_RESAMPLE = getattr(Image, "Lanczos", getattr(Image, "ANTIALIAS", Image.BILINEAR))

DATA_DIR = Path.home() / ".paste"
IMAGES_DIR = DATA_DIR / "media" / "images"
THUMB_DIR = DATA_DIR / "media" / "thumbnails"

THUMB_SIZE = (200, 200)
THUMB_QUALITY = 85


def _ensure_dirs():
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    THUMB_DIR.mkdir(parents=True, exist_ok=True)


def save_image(
    data: bytes,
    source_app: Optional[str] = None,
) -> Optional[Tuple[str, str, str]]:
    _ensure_dirs()
    try:
        uid = uuid.uuid4().hex
        img_path = IMAGES_DIR / f"{uid}.png"
        thumb_path = THUMB_DIR / f"{uid}_thumb.jpg"

        img_path.write_bytes(data)

        with Image.open(io.BytesIO(data)) as img:
            img.thumbnail(THUMB_SIZE, _RESAMPLE)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            img.save(thumb_path, "JPEG", quality=THUMB_QUALITY)

        return uid, str(img_path), str(thumb_path)
    except Exception as e:
        return None


def get_thumbnail_path(entry_id: str) -> Optional[str]:
    for ext in ("_thumb.jpg", "_thumb.png"):
        p = THUMB_DIR / f"{entry_id}{ext}"
        if p.exists():
            return str(p)
    return None


def remove_media(entry_id: str):
    for path in [
        IMAGES_DIR / f"{entry_id}.png",
        THUMB_DIR / f"{entry_id}_thumb.jpg",
    ]:
        if path.exists():
            path.unlink()


def get_media_size() -> int:
    total = 0
    for d in [IMAGES_DIR, THUMB_DIR]:
        if d.exists():
            for f in d.iterdir():
                if f.is_file():
                    total += f.stat().st_size
    return total
