import re

_PRICE_TOKEN_RE = re.compile(r"\d{1,3}(?:,\d{3})+|\d{3,}")
_HAS_LETTERS_RE = re.compile(r"[가-힣A-Za-z]{2,}")


def extract_prices(text: str) -> list[str]:
    """텍스트에서 가격 후보 토큰들을 추출. 메뉴명이면 빈 리스트."""
    cleaned = text.replace("원", " ").replace("₩", " ")
    if _HAS_LETTERS_RE.search(cleaned):
        return []
    return _PRICE_TOKEN_RE.findall(cleaned)


def is_price(text: str) -> bool:
    return len(extract_prices(text)) > 0
