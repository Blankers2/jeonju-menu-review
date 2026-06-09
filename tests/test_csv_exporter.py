import csv
from app.csv_exporter import store_to_rows, write_combined_csv


def _store():
    return {
        "store_key": "명품장어", "place_id": 13763,
        "title_extracted": "명품장어", "title_confirmed": "명품장어",
        "status": "done",
        "images": [
            {"filename": "명품장어-crop.png", "width": 600, "height": 320,
             "boxes": [], "reviewed": True,
             "rows": [
                 {"menu": "장어탕", "price": "10,000", "source_boxes": []},
                 {"menu": "계란탕", "price": "4,000", "source_boxes": []},
             ]},
        ],
    }


def test_store_to_rows_uses_confirmed_title_and_place_id():
    rows = store_to_rows(_store())
    assert rows[0] == {"place_id": 13763, "가게명": "명품장어",
                       "메뉴명": "장어탕", "가격": "10,000"}
    assert len(rows) == 2

def test_skips_empty_menu_rows():
    s = _store()
    s["images"][0]["rows"].append({"menu": "", "price": "", "source_boxes": []})
    assert len(store_to_rows(s)) == 2

def test_write_combined_csv(tmp_path):
    out = tmp_path / "all.csv"
    write_combined_csv([_store()], out)
    with open(out, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["place_id"] == "13763"
    assert rows[0]["가게명"] == "명품장어"
    assert rows[0]["메뉴명"] == "장어탕"
