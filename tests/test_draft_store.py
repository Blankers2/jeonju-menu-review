from app import draft_store


FRAGS = [
    {"org_id": "1", "ko": "산사춘", "en": "Sansachun", "ja": "サンサチュン", "zh_cn": "山楂春", "zh_tw": "山楂春"},
    {"org_id": "2", "ko": "계란탕", "en": "Egg Soup", "ja": "卵スープ", "zh_cn": "鸡蛋汤", "zh_tw": "蛋花湯"},
    {"org_id": "3", "ko": "7,000원", "en": "7,000KRW", "ja": "7,000ウォン", "zh_cn": "7,000韩元", "zh_tw": "7,000韓元"},
    {"org_id": "4", "ko": "4,000원", "en": "", "ja": "", "zh_cn": "", "zh_tw": ""},
]
META = {"place_id": 13763, "title": "명품장어", "image_url": "https://x/y.png", "width": 1897, "height": 1066}


def test_build_draft_splits_menu_and_prices():
    d = draft_store.build_draft("111227", META, FRAGS)
    assert d["place_id"] == 13763 and d["title"] == "명품장어"
    menus = {r["menu"] for r in d["rows"]}
    assert menus == {"산사춘", "계란탕"}
    # 번역 상속
    sansa = next(r for r in d["rows"] if r["menu"] == "산사춘")
    assert sansa["en"] == "Sansachun" and sansa["zh_tw"] == "山楂春"
    assert sansa["price"] == ""
    # 가격은 팔레트로
    nums = {p["number"] for p in d["prices"]}
    assert nums == {"7,000", "4,000"}


def test_save_load_and_update(tmp_path, monkeypatch):
    monkeypatch.setattr(draft_store, "DRAFTS_DIR", tmp_path)
    d = draft_store.build_draft("999", META, FRAGS)
    draft_store.save_draft(d)
    loaded = draft_store.load_draft("999")
    assert loaded["item_id"] == "999"
    assert "999" in [x["item_id"] for x in draft_store.list_drafts()]

    upd = draft_store.apply_update("999", {"reviewed": True, "rows": [
        {"menu": "산사춘", "price": "7,000", "en": "Sansachun", "ja": "", "zh_cn": "", "zh_tw": ""}]})
    assert upd["reviewed"] is True
    assert upd["rows"][0]["price"] == "7,000"
    assert draft_store.apply_update("missing", {"reviewed": True}) is None
