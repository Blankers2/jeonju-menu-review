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

    sansa = next(r for r in d["rows"] if r["menu"] == "산사춘")
    upd = draft_store.apply_update("999", {"reviewed": True, "rows": [
        {**sansa, "price": "7,000"}]})
    assert upd["reviewed"] is True
    assert upd["rows"][0]["price"] == "7,000"
    assert draft_store.apply_update("missing", {"reviewed": True}) is None


def test_apply_update_rejects_translation_edits(tmp_path, monkeypatch):
    import pytest
    monkeypatch.setattr(draft_store, "DRAFTS_DIR", tmp_path)
    d = draft_store.build_draft("777", META, FRAGS)
    draft_store.save_draft(d)
    base = d["rows"][0]
    # 허용: 번역 그대로 두고 메뉴명/가격 수정, 행 분할(번역 복제), 빈 번역 새 행
    ok_rows = [
        {**base, "menu": "산사춘(병)", "price": "7,000"},
        {**base, "menu": "산사춘(잔)", "price": "3,000"},
        {"menu": "직접추가", "price": "1,000", "en": "", "ja": "", "zh_cn": "", "zh_tw": ""},
    ]
    assert draft_store.apply_update("777", {"rows": ok_rows}) is not None
    # 거부: 번역 변조
    bad_rows = [{**base, "en": "HACKED translation"}]
    with pytest.raises(ValueError):
        draft_store.apply_update("777", {"rows": bad_rows})


def test_import_refreshes_unedited_preserves_edited(tmp_path, monkeypatch):
    monkeypatch.setattr(draft_store, "DRAFTS_DIR", tmp_path)
    pil = tmp_path / "pil.xlsx"; pil.write_text("x", encoding="utf-8")
    monkeypatch.setattr(draft_store, "PLACE_ITEM_LIST", pil)
    images = {"100": META, "200": META}
    monkeypatch.setattr(draft_store.ingest, "load_images", lambda p: images)
    monkeypatch.setattr(draft_store.ingest, "load_fragments", lambda p: {})

    r1 = draft_store.import_all()
    assert r1["created"] == 2
    assert draft_store.load_draft("100")["rows"] == []

    # 사용자가 item 100을 편집
    draft_store.apply_update("100", {"reviewed": True})

    # 나중에 두 이미지의 번역 파일이 도착
    monkeypatch.setattr(draft_store.ingest, "load_fragments", lambda p: {"100": FRAGS, "200": FRAGS})
    r2 = draft_store.import_all()

    # 100: 편집됨 -> 보존(빈 행 유지), 200: 미편집 -> 갱신(메뉴 2행)
    assert draft_store.load_draft("100")["reviewed"] is True
    assert len(draft_store.load_draft("100")["rows"]) == 0
    assert len(draft_store.load_draft("200")["rows"]) == 2
    assert r2["kept"] >= 1 and r2["refreshed"] >= 1
