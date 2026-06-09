import shutil
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import IMAGES_DIR, STATIC_DIR, STORAGE_DIR
from app import draft_store
from app.csv_exporter import write_store_csv, write_combined_csv
from app.store_resolver import load_place_index

server = FastAPI(title="Menu Finder")


@server.on_event("startup")
def _startup():
    draft_store.start_worker()


@server.post("/api/upload")
async def upload(files: list[UploadFile] = File(...)):
    saved = []
    for f in files:
        dest = IMAGES_DIR / f.filename
        with open(dest, "wb") as out:
            shutil.copyfileobj(f.file, out)
        draft_store.enqueue_image(f.filename, dest)
        saved.append(f.filename)
    return {"queued": saved}


@server.get("/api/progress")
def get_progress():
    return draft_store.progress()


@server.get("/api/places")
def get_places():
    return load_place_index()


@server.get("/api/stores")
def get_stores():
    out = []
    for s in draft_store.list_stores():
        total = sum(len(i["rows"]) for i in s["images"])
        reviewed = sum(1 for i in s["images"] if i["reviewed"])
        out.append({"store_key": s["store_key"], "place_id": s.get("place_id"),
                    "title": s.get("title_confirmed") or s.get("title_extracted"),
                    "images": len(s["images"]), "reviewed_images": reviewed,
                    "rows": total, "status": s.get("status", "pending")})
    return out


@server.get("/api/stores/{store_key}")
def get_store(store_key: str):
    s = draft_store.load_store(store_key)
    if not s:
        raise HTTPException(404, "store not found")
    return s


@server.put("/api/stores/{store_key}")
def update_store(store_key: str, payload: dict):
    s = draft_store.load_store(store_key)
    if not s:
        raise HTTPException(404, "store not found")
    for k in ("place_id", "title_confirmed", "status", "images"):
        if k in payload:
            s[k] = payload[k]
    draft_store.save_store(s)
    return s


@server.get("/api/image/{filename}")
def get_image(filename: str):
    p = IMAGES_DIR / filename
    if not p.exists():
        raise HTTPException(404, "image not found")
    return FileResponse(p)


@server.get("/api/export")
def export_all():
    stores = draft_store.list_stores()
    out = STORAGE_DIR / "menu_all.csv"
    write_combined_csv(stores, out)
    return FileResponse(out, filename="menu_all.csv", media_type="text/csv")


@server.get("/api/export/{store_key}")
def export_store(store_key: str):
    s = draft_store.load_store(store_key)
    if not s:
        raise HTTPException(404, "store not found")
    out = STORAGE_DIR / f"menu_{store_key}.csv"
    write_store_csv(s, out)
    return FileResponse(out, filename=f"menu_{store_key}.csv", media_type="text/csv")


server.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
