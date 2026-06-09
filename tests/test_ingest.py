"""실데이터(샘플 엑셀)로 인제스트 검증."""
import io
import openpyxl
from app.config import PLACE_ITEM_LIST, TRANSLATIONS_DIR
from app import ingest


def test_parse_path_meta_from_filename_and_folder():
    rel = "13764_전주성갈비/place_13764_image_111225_20260512_111947911.xlsx"
    m = ingest.parse_path_meta(rel)
    assert m["place_id"] == 13764
    assert m["item_id"] == "111225"
    assert m["title"] == "전주성갈비"


def _make_translation_bytes(item_id="111225"):
    wb = openpyxl.Workbook(); ws = wb.active
    ws.append(["code", "Item Id", "Item Org Id", "Org Content", "Image Url",
               "11_Chinese (Simplified)(中文(简体))", "12_Chinese (Traditional)(中文(繁體))",
               "17_English(English)", "30_Japanese(日本語)"])
    ws.append(["0", item_id, "1", "갈비", "https://x/y.png", "排骨", "排骨", "Galbi", "カルビ"])
    ws.append(["0", item_id, "2", "12,000원", "https://x/y.png", "", "", "", ""])
    bio = io.BytesIO(); wb.save(bio); return bio.getvalue()


def test_load_uploaded_uses_path_meta_and_image_url():
    data = _make_translation_bytes("111225")
    rel = "13764_전주성갈비/place_13764_image_111225_x.xlsx"
    frags, meta = ingest.load_uploaded([(rel, data)])
    assert "111225" in frags
    assert {f["ko"] for f in frags["111225"]} == {"갈비", "12,000원"}
    m = meta["111225"]
    assert m["place_id"] == 13764 and m["title"] == "전주성갈비"
    assert m["image_url"] == "https://x/y.png"


def test_load_images_master():
    images = ingest.load_images(PLACE_ITEM_LIST)
    assert len(images) > 100  # 240행 규모
    # 명품장어: item_id 111227 -> place 13763
    assert "111227" in images
    m = images["111227"]
    assert m["place_id"] == 13763
    assert m["title"] == "명품장어"
    assert m["image_url"].startswith("https://")


def test_load_fragments_folder():
    frs = ingest.load_fragments(TRANSLATIONS_DIR)
    assert "111227" in frs
    frags = frs["111227"]
    # 명품장어 이미지의 유효 조각(빈 행 제외) — 30개 안팎
    assert 20 <= len(frags) <= 40
    by_ko = {f["ko"]: f for f in frags}
    assert "산사춘" in by_ko
    s = by_ko["산사춘"]
    assert s["en"] and s["ja"] and s["zh_cn"] and s["zh_tw"]
    # 가격 조각도 한국어로 존재
    assert any(f["ko"] == "7,000원" for f in frags)
