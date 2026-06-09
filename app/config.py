from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
PLACE_IDS_CSV = DATA_DIR / "place_ids.csv"
STORAGE_DIR = BASE_DIR / "storage"
IMAGES_DIR = STORAGE_DIR / "images"
STORES_DIR = STORAGE_DIR / "stores"
STATIC_DIR = BASE_DIR / "app" / "static"

for _d in (STORAGE_DIR, IMAGES_DIR, STORES_DIR):
    _d.mkdir(parents=True, exist_ok=True)
