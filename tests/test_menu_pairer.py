from app.menu_pairer import is_price, extract_prices, pair_boxes


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


def _box(text, x, y, w=80, h=20):
    return {"text": text, "bbox": [x, y, w, h], "confidence": 0.9,
            "polygon": [[x, y], [x + w, y], [x + w, y + h], [x, y + h]]}


def test_single_column_pairs_menu_and_price():
    boxes = [
        _box("장어탕", 50, 100), _box("10,000원", 300, 102),
        _box("계란탕", 50, 140), _box("4,000원", 300, 141),
    ]
    rows = pair_boxes(boxes)
    simple = [{"menu": r["menu"], "price": r["price"]} for r in rows]
    assert {"menu": "장어탕", "price": "10,000"} in simple
    assert {"menu": "계란탕", "price": "4,000"} in simple

def test_two_columns_kept_separate():
    boxes = [
        _box("장어탕", 50, 100), _box("10,000원", 300, 100),
        _box("소주", 600, 100), _box("4,000원", 850, 100),
    ]
    rows = pair_boxes(boxes)
    pairs = {(r["menu"], r["price"]) for r in rows}
    assert ("장어탕", "10,000") in pairs
    assert ("소주", "4,000") in pairs
    assert ("장어탕", "4,000") not in pairs

def test_multi_price_row_expands_to_multiple_rows():
    boxes = [
        _box("냉면", 50, 100),
        _box("8,000", 250, 100), _box("9,000", 350, 100), _box("10,000", 450, 100),
    ]
    rows = pair_boxes(boxes)
    cold = [r for r in rows if r["menu"] == "냉면"]
    assert len(cold) == 3
    assert sorted(r["price"] for r in cold) == ["10,000", "8,000", "9,000"]
