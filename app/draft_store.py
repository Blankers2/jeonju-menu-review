"""item_id별 조립 드래프트의 영속화 + 초안 생성."""
import json
from pathlib import Path

from app.config import DRAFTS_DIR, PLACE_ITEM_LIST, TRANSLATIONS_DIR, SETTINGS_FILE
from app.classify import is_price, price_number
from app import ingest


def load_settings() -> dict:
    if SETTINGS_FILE.exists():
        try:
            return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_settings(settings: dict) -> None:
    SETTINGS_FILE.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")


def get_translations_dir() -> str:
    """저장된 번역 폴더 경로 또는 기본값(data/translations)."""
    return load_settings().get("translations_dir") or str(TRANSLATIONS_DIR)


def draft_path(item_id: str):
    """item_id로 드래프트 파일 경로를 찾음.

    파일명은 `<place_id>_<item_id>.json`(신형). item_id만으로 찾을 땐 glob으로 매칭
    (item_id는 전역 고유). 구형 `<item_id>.json`도 폴백 지원.
    """
    hits = list(DRAFTS_DIR.glob(f"*_{item_id}.json"))
    if hits:
        return hits[0]
    return DRAFTS_DIR / f"{item_id}.json"


def save_draft(draft: dict) -> None:
    pid = draft.get("place_id")
    iid = str(draft["item_id"])
    p = DRAFTS_DIR / (f"{pid}_{iid}.json" if pid is not None else f"{iid}.json")
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


def import_all(translations_dir: str | None = None) -> dict:
    """엑셀 인제스트 후 초안 생성/갱신.

    translations_dir: 번역본 폴더(하위폴더 재귀 스캔) 또는 합본 파일 경로.
      None이면 저장된 설정값, 그것도 없으면 기본 data/translations.
      유효한 경로면 설정에 저장(다음에 재사용).

    - 신규 item_id: 초안 생성.
    - 미편집 초안: 최신 번역조각으로 갱신(번역 파일을 나중에 추가해도 반영됨).
    - 사용자가 편집/검수한 초안: 그대로 보존.
    이미지 마스터에 있으나 조각이 없는 item_id도 빈 초안 생성(수동 입력용).
    반환: {created, refreshed, kept, total, fragment_items, source}
    """
    src = (translations_dir or "").strip() or get_translations_dir()
    src_path = Path(src)
    if not src_path.exists():
        raise FileNotFoundError(f"번역 경로를 찾을 수 없습니다: {src}")
    if translations_dir and translations_dir.strip():
        s = load_settings(); s["translations_dir"] = str(src_path); save_settings(s)

    images = ingest.load_images(PLACE_ITEM_LIST) if PLACE_ITEM_LIST.exists() else {}
    fragments = ingest.load_fragments(src_path)
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
    counts["fragment_items"] = len(fragments)
    counts["source"] = str(src_path)
    return counts


def import_uploaded(files: list) -> dict:
    """업로드된 번역본 파일들(상대경로, 바이트)로 초안 생성/갱신.

    place_id·item_id·가게명을 파일명/폴더명에서 직접 추출(마스터 조인 불필요).
    반환: {created, refreshed, kept, total, fragment_items}
    """
    frags, meta = ingest.load_uploaded(files)
    counts = {"created": 0, "refreshed": 0, "kept": 0}
    for item_id, frs in frags.items():
        counts[_upsert(item_id, meta.get(item_id, {}), frs)] += 1
    counts["total"] = len(list(DRAFTS_DIR.glob("*.json")))
    counts["fragment_items"] = len(frags)
    return counts


_TR_KEYS = ("en", "ja", "zh_cn", "zh_tw")


def _tr_tuple(row: dict) -> tuple:
    return tuple((row.get(k) or "").strip() for k in _TR_KEYS)


def _validate_translations(existing_rows: list, new_rows: list) -> None:
    """번역 4종은 절대 수정 금지. 기존 행의 번역 묶음을 그대로 쓰거나(분할/복제 허용)
    전부 빈 값(수동 추가 행)이어야 함. 위반 시 ValueError."""
    allowed = {_tr_tuple(r) for r in existing_rows}
    allowed.add(("", "", "", ""))
    for r in new_rows:
        if _tr_tuple(r) not in allowed:
            raise ValueError(
                f"번역 컬럼은 수정할 수 없습니다 (메뉴: {r.get('menu', '')!r})")


def apply_update(item_id: str, payload: dict) -> dict | None:
    draft = load_draft(item_id)
    if draft is None:
        return None
    # 번역 수정은 기본 차단. UI의 "번역 수정" 토글을 켠 경우에만 허용
    # (조각 머지 시 번역도 함께 머지해야 하는 케이스).
    if "rows" in payload and not payload.get("allow_translation_edit"):
        _validate_translations(draft.get("rows", []), payload["rows"])
    for k in ("rows", "title", "reviewed", "status", "place_id"):
        if k in payload:
            draft[k] = payload[k]
    draft["edited"] = True  # 사용자 편집 표시 → 이후 재가져오기에서 보존
    save_draft(draft)
    return draft
