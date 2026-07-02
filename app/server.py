from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import json
import re
import sys

from app.config import BASE_DIR, DRAFTS_DIR, STATIC_DIR, STORAGE_DIR
from app import draft_store
from app.xlsx_exporter import write_workbook

server = FastAPI(title="Menu Finder")

_CITY_FIXES = STORAGE_DIR / "city_fixes.json"


@server.get("/api/fixes/{item_id}")
def get_fixes(item_id: str):
    """해당 item이 속한 place의 시청 수정지시 코멘트(있으면)."""
    if not _CITY_FIXES.exists():
        return {}
    d = draft_store.load_draft(item_id)
    if not d:
        return {}
    fixes = json.loads(_CITY_FIXES.read_text(encoding="utf-8"))
    return fixes.get(str(d.get("place_id")), {})


# ---- 카테고리 추천 (번역조각 + 시청 코멘트 기반) ----
_LANGS = ("en", "ja", "zh_cn", "zh_tw")
# 코멘트에서 카테고리로 볼 만한 토큰: "…류/…메뉴/…특선/…안주" + 고정어
_CAT_TOKEN = re.compile(r"[가-힣]{1,8}(?:류|메뉴|특선|안주)")
_CAT_FIXED = ("음료", "후식", "식사", "주류", "런치", "디너", "세트", "사이드", "점심특선")
_CAT_BLACKLIST = {"분류", "종류", "메뉴"}  # "카테고리별 분류" 등 지시문 단어
_FRAG_CACHE: dict = {}


def _fragments() -> tuple[dict, dict]:
    """전주시청 번역모음 조각을 1회 로드해 캐시.

    반환: (by_item{item_id:[frag]}, global_dict{ko:{lang:최빈}}).
    global_dict은 카테고리 등 공통 modifier의 크로스 재사용에만 씀(스펙 허용).
    """
    if "by_item" not in _FRAG_CACHE:
        try:
            sys.path.insert(0, str(BASE_DIR / "tools"))
            from fragment_dict import load as load_frag
            by_item, global_dict = load_frag()
        except Exception:
            by_item, global_dict = {}, {}
        _FRAG_CACHE["by_item"] = by_item
        _FRAG_CACHE["global"] = global_dict
    return _FRAG_CACHE["by_item"], _FRAG_CACHE["global"]


def _is_cat_like(ko: str) -> bool:
    if not (2 <= len(ko) <= 10) or ko in _CAT_BLACKLIST:
        return False
    if any(ch.isdigit() for ch in ko):
        return False
    return ko.endswith(("류", "메뉴", "특선", "안주")) or ko in _CAT_FIXED


@server.get("/api/categories/{item_id}")
def get_categories(item_id: str):
    """해당 place의 추천 카테고리 후보.

    출처: ①시청 코멘트에 언급된 카테고리명 ②place 번역조각 중 카테고리성 어휘.
    번역조각이 있는 후보만 4언어 번역을 동봉(has_fragment). 임의번역 없음.
    """
    d = draft_store.load_draft(item_id)
    if d is None:
        raise HTTPException(404, "draft not found")
    pid = d.get("place_id")
    by_item, global_dict = _fragments()
    # place의 모든 item 조각 → ko별 번역(먼저 나온 것 우선)
    frag: dict[str, dict] = {}
    for p in sorted(DRAFTS_DIR.glob(f"{pid}_*.json")):
        iid = p.stem.split("_", 1)[1]
        for fr in by_item.get(iid, []):
            ko = (fr.get("ko") or "").strip()
            if ko and ko not in frag:
                frag[ko] = {l: (fr.get(l) or "").strip() for l in _LANGS}
    # ① 시청 코멘트에서 후보 추출
    ordered: list[str] = []
    if _CITY_FIXES.exists():
        fixes = json.loads(_CITY_FIXES.read_text(encoding="utf-8")).get(str(pid), {})
        text = "\n".join(fixes.get("comments", []))
        for m in _CAT_TOKEN.finditer(text):
            t = m.group(0)
            if t not in _CAT_BLACKLIST and t not in ordered:
                ordered.append(t)
        for w in _CAT_FIXED:
            if w in text and w not in ordered:
                ordered.append(w)
    # ② place 조각 중 카테고리성 어휘
    for ko in frag:
        if _is_cat_like(ko) and ko not in ordered:
            ordered.append(ko)
    # ③ 기본 분류: 카테고리 없는 업소는 "메뉴"/"주류" 둘로 나눔 — 항상 추천에 포함
    for w in ("메뉴", "주류"):
        if w not in ordered:
            ordered.append(w)
    out = []
    for ko in ordered:
        # place 자체 조각 우선, 없으면 전역 조각(카테고리 공통어휘 크로스 재사용)
        tr = frag.get(ko)
        src = "place"
        if not (tr and any(tr.values())):
            tr = global_dict.get(ko)
            src = "global"
        has = bool(tr and any(tr.values()))
        out.append({"ko": ko, "has_fragment": has, "source": src if has else "",
                    **(tr or {l: "" for l in _LANGS})})
    return {"suggestions": out}


@server.get("/api/settings")
def get_settings():
    """저장된 경로 등 설정. translations_dir는 기본값으로 폴백."""
    s = draft_store.load_settings()
    s["translations_dir"] = draft_store.get_translations_dir()
    return s


@server.post("/api/import")
def do_import(payload: dict | None = None):
    """엑셀(이미지 마스터 + 번역폴더)을 인제스트해 초안 생성/갱신.

    body(JSON, 선택): {"translations_dir": "<폴더 또는 합본파일 경로>"}.
    경로를 주면 설정에 저장돼 다음에 재사용됨.
    """
    translations_dir = (payload or {}).get("translations_dir") if payload else None
    try:
        return draft_store.import_all(translations_dir)
    except FileNotFoundError as e:
        raise HTTPException(400, str(e))


def _expand_uploads(uploads):
    """(rel_path, bytes) 목록을 펼침. .zip은 내부 .xlsx로 전개, .gsheet는 건너뜀.

    반환: (xlsx_pairs, skipped_gsheet)
    """
    import io
    import zipfile

    out = []
    skipped = 0
    for rel, data in uploads:
        low = rel.lower()
        base = rel.replace("\\", "/").split("/")[-1]
        if low.endswith(".zip"):
            try:
                z = zipfile.ZipFile(io.BytesIO(data))
            except Exception:
                continue
            for name in z.namelist():
                nl = name.lower()
                member = name.split("/")[-1]
                if nl.endswith("/") or member.startswith("~$"):
                    continue
                if nl.endswith(".xlsx"):
                    out.append((name, z.read(name)))
                elif nl.endswith(".gsheet"):
                    skipped += 1
        elif low.endswith(".xlsx") and not base.startswith("~$"):
            out.append((rel, data))
        elif low.endswith(".gsheet"):
            skipped += 1
    return out, skipped


@server.post("/api/upload_translations")
async def upload_translations(files: list[UploadFile] = File(...),
                              paths: list[str] = Form(default=[])):
    """번역본 파일/폴더(또는 Drive 다운로드 .zip)를 업로드 -> 초안 생성/갱신.

    paths: 각 파일의 상대경로(폴더 포함, files와 같은 순서). place_id/item_id/가게명을
    파일명·폴더명에서 추출하므로 마스터 조인 없이 동작. .gsheet(구글시트 포인터)는 건너뜀.
    """
    uploads = []
    for i, f in enumerate(files):
        rel = (paths[i] if i < len(paths) else f.filename) or f.filename
        uploads.append((rel, await f.read()))
    pairs, skipped = _expand_uploads(uploads)
    result = draft_store.import_uploaded(pairs)
    result["skipped_gsheet"] = skipped
    return result


@server.get("/api/images")
def list_images():
    """사이드바용 요약 목록."""
    out = []
    for d in draft_store.list_drafts():
        out.append({
            "item_id": d["item_id"],
            "place_id": d.get("place_id"),
            "title": d.get("title", ""),
            "rows": len(d.get("rows", [])),
            "reviewed": d.get("reviewed", False),
        })
    out.sort(key=lambda x: (x["place_id"] if x["place_id"] is not None else 1 << 30,
                            int(x["item_id"]) if str(x["item_id"]).isdigit() else 0))
    return out


@server.get("/api/images/{item_id}")
def get_image_draft(item_id: str):
    d = draft_store.load_draft(item_id)
    if d is None:
        raise HTTPException(404, "draft not found")
    return d


@server.put("/api/images/{item_id}")
def update_image_draft(item_id: str, payload: dict):
    try:
        d = draft_store.apply_update(item_id, payload)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if d is None:
        raise HTTPException(404, "draft not found")
    return d


def _cat_lookup(pid, ko: str) -> dict | None:
    """분류 번역: place 조각 우선 → 전역 조각(공통어휘). 조각 없으면 None(빈칸)."""
    by_item, global_dict = _fragments()
    for p in sorted(DRAFTS_DIR.glob(f"{pid}_*.json")):
        iid = p.stem.split("_", 1)[1]
        for fr in by_item.get(iid, []):
            if (fr.get("ko") or "").strip() == ko:
                tr = {l: (fr.get(l) or "").strip() for l in _LANGS}
                if any(tr.values()):
                    return tr
    return global_dict.get(ko)


@server.get("/api/export")
def export_all():
    out = STORAGE_DIR / "menu_all.xlsx"
    write_workbook(draft_store.list_drafts(), out, cat_lookup=_cat_lookup)
    return FileResponse(
        out, filename="menu_all.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


server.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
