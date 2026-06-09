"""실데이터(샘플 엑셀)로 인제스트 검증."""
from app.config import PLACE_ITEM_LIST, TRANSLATIONS_DIR
from app import ingest


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
