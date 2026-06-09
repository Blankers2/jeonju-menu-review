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


def _upsert(item_id: str, meta: dict, frs: list[dict]) -> str:
    """초안 생성/갱신. 사용자가 편집한 드래프트(edited)는 보존, 손 안 댄 것은 최신 조각으로 갱신.

    반환: "created" | "refreshed" | "kept"
    """
    existing = load_draft(item_id)
    if existing is None:
        save_draft(build_draft(item_id, meta, frs))
        return "created"
    if existing.get("edited"):
        return "kept"
    # 미편집 초안: 최신 번역조각/메타로 재생성(나중에 번역 파일을 추가한 경우 반영)
    save_draft(build_draft(item_id, meta or {
        "place_id": existing.get("place_id"), "title": existing.get("title"),
        "image_url": existing.get("image_url"), "width": existing.get("width"),
        "height": existing.get("height"),
    }, frs))
    return "refreshed"


def import_all() -> dict:
    """엑셀 인제스트 후 초안 생성/갱신.

    - 신규 item_id: 초안 생성.
    - 미편집 초안: 최신 번역조각으로 갱신(번역 파일을 나중에 추가해도 반영됨).
    - 사용자가 편집/검수한 초안: 그대로 보존.
    이미지 마스터에 있으나 조각이 없는 item_id도 빈 초안 생성(수동 입력용).
    반환: {created, refreshed, kept, total}
    """
    images = ingest.load_images(PLACE_ITEM_LIST) if PLACE_ITEM_LIST.exists() else {}
    fragments = ingest.load_fragments(TRANSLATIONS_DIR)
    counts = {"created": 0, "refreshed": 0, "kept": 0}
    seen = set()
    for item_id, meta in images.items():
        counts[_upsert(item_id, meta, fragments.get(item_id, []))] += 1
        seen.add(item_id)
    # 마스터엔 없지만 번역조각만 있는 item_id도 포용
    for item_id, frs in fragments.items():
        if item_id in seen:
            continue
        counts[_upsert(item_id, {}, frs)] += 1
    counts["total"] = len(list(DRAFTS_DIR.glob("*.json")))
    return counts


def apply_update(item_id: str, payload: dict) -> dict | None:
    draft = load_draft(item_id)
    if draft is None:
        return None
    for k in ("rows", "title", "reviewed", "status", "place_id"):
        if k in payload:
            draft[k] = payload[k]
    draft["edited"] = True  # 사용자 편집 표시 → 이후 재가져오기에서 보존
    save_draft(draft)
    return draft
