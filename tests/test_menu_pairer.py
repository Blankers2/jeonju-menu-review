from app.menu_pairer import is_price, extract_prices


def test_is_price_various_formats():
    assert is_price("10,000원")
    assert is_price("10000")
    assert is_price("5,000")
    assert is_price("₩12,000")
    assert not is_price("장어탕")
    assert not is_price("식사류")

def test_extract_multiple_prices_in_one_cell():
    assert extract_prices("10,000 / 13,000 / 16,000") == ["10,000", "13,000", "16,000"]
    assert extract_prices("8000") == ["8000"]
    assert extract_prices("장어탕") == []
