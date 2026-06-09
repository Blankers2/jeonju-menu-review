from app.classify import is_price, price_number


def test_is_price_true_cases():
    assert is_price("7,000원")
    assert is_price("2,000원")
    assert is_price("65,000")
    assert is_price("₩12,000")


def test_is_price_false_cases():
    assert not is_price("산사춘")
    assert not is_price("장어즙 (30포) 65,000원")  # 글자 포함 -> 메뉴
    assert not is_price("식사")
    assert not is_price("")
    assert not is_price(None)


def test_price_number_extracts_digits():
    assert price_number("7,000원") == "7,000"
    assert price_number("65,000") == "65,000"
    assert price_number("산사춘") == ""
