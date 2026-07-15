import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.utils.url import contains_url, is_url_content


def test_contains_url_finds_addresses_inside_text():
    assert contains_url("Open https://example.com/path for details")
    assert contains_url("官网：www.example.cn/docs")
    assert contains_url("Repository example.io/project")


def test_contains_url_does_not_match_normal_text():
    assert not contains_url("ordinary clipboard text")
    assert not contains_url("user@example.com")


def test_is_url_content_requires_the_whole_value_to_be_an_address():
    assert is_url_content("https://example.com")
    assert is_url_content("example.com/path")
    assert not is_url_content("See https://example.com")
