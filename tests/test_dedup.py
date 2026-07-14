import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.utils.dedup import normalize_text, dhash, hamming_distance, is_duplicate_image
import hashlib


class TestDedup:
    def test_normalize_text_strips_whitespace(self):
        assert normalize_text("  hello  ") == "hello"

    def test_normalize_text_normalizes_newlines(self):
        result = normalize_text("a\r\nb\r\nc")
        assert result == "a\nb\nc"

    def test_normalize_text_collapses_spaces(self):
        result = normalize_text("hello    world")
        assert result == "hello world"

    def test_dhash_different_images(self):
        from PIL import Image, ImageDraw
        import io

        def _make_image(draw_fn):
            img = Image.new("L", (32, 32), 128)
            drawer = ImageDraw.Draw(img)
            draw_fn(drawer)
            buf = io.BytesIO()
            img.save(buf, "PNG")
            return buf.getvalue()

        data1 = _make_image(lambda d: d.rectangle([0, 0, 15, 31], fill=0))
        data2 = _make_image(lambda d: d.rectangle([16, 0, 31, 31], fill=0))
        h1 = dhash(data1)
        h2 = dhash(data2)
        assert hamming_distance(h1, h2) > 0

    def test_dhash_same_image(self):
        data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        h1 = dhash(data)
        h2 = dhash(data)
        assert hamming_distance(h1, h2) == 0

    def test_normalize_text_removes_extra_newlines(self):
        text = "line1\n\n\n\nline2"
        result = normalize_text(text)
        assert result == "line1\n\nline2"
