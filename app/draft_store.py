import json
import threading
import queue
from pathlib import Path

from app.config import STORES_DIR, IMAGES_DIR
from app.store_resolver import (
    normalize_store_name, load_place_index, match_place, AUTO_CONFIRM_SCORE,
)
from app.menu_pairer import pair_boxes
from app.ocr_engine import image_size


def _safe(name: str) -> str:
    return "".join(c if c.isalnum() or c in "._-가-힣" else "_" for c in name)


def store_path(store_key: str) -> Path:
    return STORES_DIR / f"{_safe(store_key)}.json"


def save_store(store: dict) -> None:
    p = store_path(store["store_key"])
    p.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")


def load_store(store_key: str) -> dict | None:
    p = store_path(store_key)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def list_stores() -> list[dict]:
    out = []
    for p in sorted(STORES_DIR.glob("*.json")):
        out.append(json.loads(p.read_text(encoding="utf-8")))
    return out


# ---- OCR 큐 (백그라운드 단일 워커) ----
_job_q: "queue.Queue[tuple[str, Path]]" = queue.Queue()
_progress = {"total": 0, "done": 0}
_lock = threading.Lock()
_place_index = None
_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        from app.ocr_engine import PaddleOcrEngine
        _engine = PaddleOcrEngine()
    return _engine


def _get_index():
    global _place_index
    if _place_index is None:
        _place_index = load_place_index()
    return _place_index


def enqueue_image(filename: str, path: Path) -> None:
    with _lock:
        _progress["total"] += 1
    _job_q.put((filename, path))


def progress() -> dict:
    with _lock:
        return dict(_progress)


def _ensure_store(store_key: str) -> dict:
    store = load_store(store_key)
    if store:
        return store
    cands = match_place(store_key, _get_index())
    place_id = cands[0]["place_id"] if cands and cands[0]["score"] >= AUTO_CONFIRM_SCORE else None
    title = cands[0]["title"] if place_id else store_key
    return {"store_key": store_key, "place_id": place_id,
            "title_extracted": title, "title_confirmed": None,
            "status": "pending", "candidates": cands, "images": []}


def _process(filename: str, path: Path) -> None:
    store_key = normalize_store_name(filename)
    store = _ensure_store(store_key)
    boxes = _get_engine().read(path)
    w, h = image_size(path)
    store["images"] = [im for im in store["images"] if im["filename"] != filename]
    store["images"].append({
        "filename": filename, "width": w, "height": h,
        "boxes": boxes, "rows": pair_boxes(boxes), "reviewed": False,
    })
    save_store(store)


def _worker() -> None:
    while True:
        filename, path = _job_q.get()
        try:
            _process(filename, path)
        except Exception as e:
            print(f"[OCR ERROR] {filename}: {e}")
        finally:
            with _lock:
                _progress["done"] += 1
            _job_q.task_done()


def start_worker() -> None:
    t = threading.Thread(target=_worker, daemon=True)
    t.start()
