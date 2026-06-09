from app import draft_store
from app.menu_pairer import pair_boxes
from app.csv_exporter import store_to_rows


def test_save_and_load_store(tmp_path, monkeypatch):
    monkeypatch.setattr(draft_store, "STORES_DIR", tmp_path)
    store = {"store_key": "명문", "place_id": 13426,
             "title_extracted": "명문", "title_confirmed": None,
             "status": "pending", "images": []}
    draft_store.save_store(store)
    loaded = draft_store.load_store("명문")
    assert loaded["place_id"] == 13426
    assert "명문" in [s["store_key"] for s in draft_store.list_stores()]


def test_pairing_to_export_endtoend():
    boxes = [
        {"text": "장어탕", "bbox": [50, 100, 80, 20], "confidence": 0.9, "polygon": []},
        {"text": "10,000원", "bbox": [300, 100, 80, 20], "confidence": 0.9, "polygon": []},
    ]
    rows = pair_boxes(boxes)
    store = {"store_key": "x", "place_id": 1, "title_extracted": "x",
             "title_confirmed": "x", "status": "done",
             "images": [{"filename": "x.png", "width": 600, "height": 320,
                         "boxes": boxes, "rows": rows, "reviewed": True}]}
    exported = store_to_rows(store)
    assert {"place_id": 1, "가게명": "x", "메뉴명": "장어탕", "가격": "10,000"} in exported
