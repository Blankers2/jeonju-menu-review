from app import draft_store


def test_save_and_load_store(tmp_path, monkeypatch):
    monkeypatch.setattr(draft_store, "STORES_DIR", tmp_path)
    store = {"store_key": "명문", "place_id": 13426,
             "title_extracted": "명문", "title_confirmed": None,
             "status": "pending", "images": []}
    draft_store.save_store(store)
    loaded = draft_store.load_store("명문")
    assert loaded["place_id"] == 13426
    assert "명문" in [s["store_key"] for s in draft_store.list_stores()]
