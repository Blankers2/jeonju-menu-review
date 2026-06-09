from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import STATIC_DIR, STORAGE_DIR
from app import draft_store
from app.xlsx_exporter import write_workbook

server = FastAPI(title="Menu Finder")


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
    d = draft_store.apply_update(item_id, payload)
    if d is None:
        raise HTTPException(404, "draft not found")
    return d


@server.get("/api/export")
def export_all():
    out = STORAGE_DIR / "menu_all.xlsx"
    write_workbook(draft_store.list_drafts(), out)
    return FileResponse(
        out, filename="menu_all.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


server.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
