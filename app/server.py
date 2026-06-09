from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import STATIC_DIR, STORAGE_DIR
from app import draft_store
from app.xlsx_exporter import write_workbook

server = FastAPI(title="Menu Finder")


@server.post("/api/import")
def do_import():
    """엑셀(이미지 마스터 + 번역폴더)을 인제스트해 초안 생성."""
    return draft_store.import_all()


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
