from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
PLACE_ITEM_LIST = DATA_DIR / "place_item_list.xlsx"
TRANSLATIONS_DIR = DATA_DIR / "translations"
STORAGE_DIR = BASE_DIR / "storage"
DRAFTS_DIR = STORAGE_DIR / "drafts"
SETTINGS_FILE = STORAGE_DIR / "settings.json"
STATIC_DIR = BASE_DIR / "app" / "static"

for _d in (DATA_DIR, TRANSLATIONS_DIR, STORAGE_DIR, DRAFTS_DIR):
    _d.mkdir(parents=True, exist_ok=True)
