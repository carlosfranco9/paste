import io
import re
from PIL import Image

_RESAMPLE = getattr(Image, "Lanczos", getattr(Image, "ANTIALIAS", Image.BILINEAR))


def normalize_text(text: str) -> str:
    text = text.strip()
    text = re.sub(r'\r\n', '\n', text)
    text = re.sub(r'\r', '\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def dhash(image_data: bytes, hash_size: int = 8) -> int:
    try:
        with Image.open(io.BytesIO(image_data)) as img:
            img = img.convert("L").resize((hash_size + 1, hash_size), _RESAMPLE)
            pixels = list(img.getdata())
            diff = []
            for row in range(hash_size):
                for col in range(hash_size):
                    idx = row * (hash_size + 1) + col
                    diff.append(pixels[idx] > pixels[idx + 1])
            return sum(2 ** i for i, v in enumerate(diff) if v)
    except Exception:
        return 0


def hamming_distance(h1: int, h2: int) -> int:
    return bin(h1 ^ h2).count("1")


def is_duplicate_image(data1: bytes, data2: bytes, threshold: int = 10) -> bool:
    h1 = dhash(data1)
    h2 = dhash(data2)
    return hamming_distance(h1, h2) <= threshold
