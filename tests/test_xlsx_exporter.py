import openpyxl
from app.xlsx_exporter import draft_to_rows, write_workbook, HEADERS


def _draft(item_id, place_id, title, rows):
    return {"item_id": item_id, "place_id": place_id, "title": title,
            "image_url": f"https://x/{item_id}.png", "rows": rows}


def test_draft_to_rows_skips_empty_and_maps_columns():
    d = _draft("111227", 13763, "명품장어", [
        {"category": "주류", "menu": "산사춘", "price": "7,000", "en": "Sansachun Hawthron Wine",
         "ja": "サンサチュン", "zh_cn": "山楂春", "zh_tw": "山楂春"},
        {"menu": "", "price": "", "en": "", "ja": "", "zh_cn": "", "zh_tw": ""},
    ])
    rows = draft_to_rows(d)
    assert len(rows) == 1
    # cat_lookup 없음 → 분류 번역 4열은 빈칸(임의번역 금지)
    assert rows[0] == [13763, "명품장어", "111227", "주류", "", "", "", "",
                       "산사춘", "7,000",
                       "Sansachun Hawthron Wine", "サンサチュン", "山楂春", "山楂春",
                       "https://x/111227.png"]


def test_draft_to_rows_category_translation_via_lookup():
    d = _draft("111227", 13763, "명품장어", [
        {"category": "주류", "menu": "산사춘", "price": "7,000",
         "en": "Sansachun", "ja": "サンサチュン", "zh_cn": "山楂春", "zh_tw": "山楂春"},
    ])
    def lookup(pid, ko):
        assert pid == 13763
        return {"en": "Alcoholic Beverages", "ja": "アルコール類",
                "zh_cn": "酒类", "zh_tw": "酒類"} if ko == "주류" else None
    rows = draft_to_rows(d, cat_lookup=lookup)
    assert rows[0][3:8] == ["주류", "Alcoholic Beverages", "アルコール類", "酒类", "酒類"]


def test_write_workbook_sorted_with_header(tmp_path):
    drafts = [
        _draft("111227", 13763, "명품장어", [{"menu": "소주", "price": "4,000",
            "en": "Soju", "ja": "焼酎", "zh_cn": "烧酒", "zh_tw": "燒酒"}]),
        _draft("105716", 13430, "한양불고기", [{"menu": "불고기", "price": "15,000",
            "en": "Bulgogi", "ja": "", "zh_cn": "", "zh_tw": ""}]),
    ]
    out = tmp_path / "menu_all.xlsx"
    n = write_workbook(drafts, out)
    assert n == 2
    wb = openpyxl.load_workbook(out)
    ws = wb.active
    data = list(ws.iter_rows(values_only=True))
    assert list(data[0]) == HEADERS
    # place_id 13430 먼저 정렬 (분류+분류번역 4열 추가로 메뉴명은 index 8)
    assert data[1][0] == 13430 and data[1][8] == "불고기"
    assert data[2][0] == 13763 and data[2][8] == "소주"
