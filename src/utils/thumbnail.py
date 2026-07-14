import io
from pathlib import Path

from typing import Tuple
from PIL import Image

_RESAMPLE = getattr(Image, "Lanczos", getattr(Image, "ANTIALIAS", Image.BILINEAR))

THUMB_SIZE = (200, 200)
THUMB_QUALITY = 85


def generate_thumbnail(
    image_data: bytes,
    output_path: str,
    size: "Tuple[int, int]" = THUMB_SIZE,
    ) -> bool:
    try:
        with Image.open(io.BytesIO(image_data)) as img:
            img.thumbnail(size, _RESAMPLE)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            img.save(output_path, "JPEG", quality=THUMB_QUALITY)
        return True
    except Exception:
        return False


def generate_thumbnail_from_file(
    input_path: str,
    output_path: str,
    size: "Tuple[int, int]" = THUMB_SIZE,
) -> bool:
    try:
        with Image.open(input_path) as img:
            img.thumbnail(size, _RESAMPLE)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            img.save(output_path, "JPEG", quality=THUMB_QUALITY)
        return True
    except Exception:
        return False
