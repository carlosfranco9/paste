import re


_HOST = (
    r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"(?:com\.cn|net\.cn|org\.cn|com|org|net|edu|gov|io|dev|app|ai|"
    r"cn|co|me|info|biz|xyz|top|site|online)"
)
_URL_BODY = (
    rf"(?:"
    rf"(?:https?|ftp)://[^\s<>\"']+"
    rf"|www\.[^\s<>\"']+"
    rf"|{_HOST}(?:[/:?#][^\s<>\"']*)?"
    rf")"
)
URL_PATTERN = re.compile(rf"(?i)(?<![\w@]){_URL_BODY}")
FULL_URL_PATTERN = re.compile(rf"(?i)^{_URL_BODY}$")


def contains_url(value):
    if not isinstance(value, str) or not value:
        return False
    return URL_PATTERN.search(value) is not None


def is_url_content(value):
    if not isinstance(value, str):
        return False
    return FULL_URL_PATTERN.fullmatch(value.strip()) is not None
