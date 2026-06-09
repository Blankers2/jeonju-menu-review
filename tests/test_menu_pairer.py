from app.menu_pairer import is_price, extract_prices, pair_boxes, split_menu_price


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


# ── split_menu_price tests ──────────────────────────────────────────────────

def test_split_menu_price_merged_box():
    assert split_menu_price("계란탕4,000원") == ("계란탕", ["4,000"])
    assert split_menu_price("장어탕10,000원") == ("장어탕", ["10,000"])
    assert split_menu_price("소주4,000원") == ("소주", ["4,000"])

def test_split_pure_menu():
    assert split_menu_price("장어탕") == ("장어탕", [])
    assert split_menu_price("식사류") == ("식사류", [])

def test_split_pure_price():
    assert split_menu_price("10,000원") == ("", ["10,000"])
    assert split_menu_price("8000") == ("", ["8000"])

def test_split_keeps_small_numbers_in_menu():
    # 메뉴명에 든 작은 숫자/수량은 가격이 아님
    assert split_menu_price("명가등심1호") == ("명가등심1호", [])
    assert split_menu_price("공기밥") == ("공기밥", [])

def test_split_quantity_not_price_but_real_price_extracted():
    # "장어즙 (30포) 65,000원" → 메뉴는 수량 포함 유지, 가격은 65,000만
    menu, prices = split_menu_price("장어즙 (30포) 65,000원")
    assert prices == ["65,000"]
    assert "장어즙" in menu and "30" in menu  # 수량 30은 메뉴쪽에 남음


# ── merged-box pairing test ─────────────────────────────────────────────────

def test_pair_boxes_handles_merged_menu_price_boxes():
    boxes = [
        {"text": "계란탕4,000원", "bbox": [50, 100, 120, 20], "confidence": 0.9, "polygon": []},
        {"text": "소주4,000원", "bbox": [600, 100, 120, 20], "confidence": 0.9, "polygon": []},
    ]
    rows = pair_boxes(boxes)
    pairs = {(r["menu"], r["price"]) for r in rows}
    assert ("계란탕", "4,000") in pairs
    assert ("소주", "4,000") in pairs


# ── phone number masking tests (Fix A) ─────────────────────────────────────

def test_phone_number_not_treated_as_price():
    menu, prices = split_menu_price("문의 063-123-4567")
    assert prices == []
    menu2, prices2 = split_menu_price("예약 063.251.3535")
    assert prices2 == []

def test_phone_then_real_price():
    menu, prices = split_menu_price("장어탕 10,000원 (063-251-3535)")
    assert prices == ["10,000"]

def test_extract_prices_ignores_phone():
    from app.menu_pairer import extract_prices
    assert extract_prices("063-123-4567") == []
