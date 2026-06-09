import csv
from pathlib import Path

FIELDS = ["place_id", "가게명", "메뉴명", "가격"]


def store_to_rows(store: dict) -> list[dict]:
    title = store.get("title_confirmed") or store.get("title_extracted") or ""
    place_id = store.get("place_id")
    out = []
    for img in store.get("images", []):
        for row in img.get("rows", []):
            menu = (row.get("menu") or "").strip()
            price = (row.get("price") or "").strip()
            if not menu and not price:
                continue
            out.append({"place_id": place_id, "가게명": title,
                        "메뉴명": menu, "가격": price})
    return out


def write_store_csv(store: dict, path: Path) -> None:
    _write(store_to_rows(store), path)


def write_combined_csv(stores: list[dict], path: Path) -> None:
    rows = []
    for s in stores:
        rows.extend(store_to_rows(s))
    _write(rows, path)


def _write(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
