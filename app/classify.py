"""번역 조각(텍스트)을 가격 vs 메뉴명으로 분류."""
import re

# 가격 토큰: 콤마 묶음(1,000) 또는 3자리 이상 숫자
_PRICE_TOKEN_RE = re.compile(r"\d{1,3}(?:,\d{3})+|\d{3,}")
# 한글/로마자가 2글자 이상 섞여 있으면 메뉴명(또는 메뉴+가격 혼합)으로 간주
_HAS_WORDS_RE = re.compile(r"[가-힣A-Za-z]{2,}")


def is_price(text) -> bool:
    """글자 없이 숫자(콤마/원/공백/통화기호 허용) 위주이면 가격 조각.

    예) "7,000원", "2,000원", "65,000" -> True
        "산사춘", "장어즙 (30포) 65,000원"(글자 포함) -> False
    """
    if text is None:
        return False
    cleaned = str(text).replace("원", " ").replace("₩", " ").replace("KRW", " ")
    if _HAS_WORDS_RE.search(cleaned):
        return False
    return bool(_PRICE_TOKEN_RE.search(cleaned))


def price_number(text) -> str:
    """가격 조각에서 숫자 부분만 추출. 예 "7,000원" -> "7,000". 없으면 "" ."""
    if text is None:
        return ""
    m = _PRICE_TOKEN_RE.search(str(text).replace("원", " ").replace("₩", " "))
    return m.group() if m else ""
