"""item_id별 조립 드래프트의 영속화 + 초안 생성."""
import json

from app.config import DRAFTS_DIR, PLACE_ITEM_LIST, TRANSLATIONS_DIR
from app.classify import is_price, price_number
from app import ingest


def draft_path(item_id: str):
    return DRAFTS_DIR / f"{item_id}.json"


def save_draft(draft: dict) -> None:
    p = draft_path(str(draft["item_id"]))
    p.write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")


def load_draft(item_id: str) -> dict | None:
    p = draft_path(str(item_id))
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def list_drafts() -> list[dict]:
    out = []
    for p in sorted(DRAFTS_DIR.glob("*.json")):
        out.append(json.loads(p.read_text(encoding="utf-8")))
    return out


def build_draft(item_id: str, image_meta: dict, fragments: list[dict]) -> dict:
    """이미지 메타 + 번역조각 -> 초안 드래프트.

    - 가격형 조각 -> prices 팔레트 [{text, number}]
    - 그 외 조각  -> 메뉴행(번역 상속) rows [{menu, price:"", en, ja, zh_cn, zh_tw, org_id}]
    """
    rows, prices = [], []
    for fr in fragments or []:
        ko = (fr.get("ko") or "").strip()
        if ko == "":
            continue
        if is_price(ko):
            prices.append({"text": ko, "number": price_number(ko)})
        else:
            rows.append({
                "menu": ko, "price": "",
                "en": fr.get("en", ""), "ja": fr.get("ja", ""),
                "zh_cn": fr.get("zh_cn", ""), "zh_tw": fr.get("zh_tw", ""),
                "org_id": fr.get("org_id", ""),
            })
    return {
        "item_id": str(item_id),
        "place_id": (image_meta or {}).get("place_id"),
        "title": (image_meta or {}).get("title", ""),
        "image_url": (image_meta or {}).get("image_url", ""),
        "width": (image_meta or {}).get("width"),
        "height": (image_meta or {}).get("height"),
        "rows": rows,
        "prices": prices,
        "reviewed": False,
        "status": "pending",
    }


def import_all() -> dict:
    """엑셀 인제스트 후, 드래프트가 없는 item_id만 초안 생성(기존 편집 보존).

    이미지 마스터에 있으나 번역조각이 없는 item_id도 빈 초안 생성(수동 입력용).
    반환: {created, total}
    """
    images = ingest.load_images(PLACE_ITEM_LIST) if PLACE_ITEM_LIST.exists() else {}
    fragments = ingest.load_fragments(TRANSLATIONS_DIR)
    created = 0
    for item_id, meta in images.items():
        if load_draft(item_id) is not None:
            continue
        save_draft(build_draft(item_id, meta, fragments.get(item_id, [])))
        created += 1
    # 마스터엔 없지만 번역조각만 있는 item_id도 포용
    for item_id, frs in fragments.items():
        if item_id in images:
            continue
        if load_draft(item_id) is not None:
            continue
        save_draft(build_draft(item_id, {}, frs))
        created += 1
    return {"created": created, "total": len(list(DRAFTS_DIR.glob("*.json")))}


def apply_update(item_id: str, payload: dict) -> dict | None:
    draft = load_draft(item_id)
    if draft is None:
        return None
    for k in ("rows", "title", "reviewed", "status", "place_id"):
        if k in payload:
            draft[k] = payload[k]
    save_draft(draft)
    return draft
