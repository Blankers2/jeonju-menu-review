"""storage/drafts → docs/data.json (시청 최종검수용 정적 사이트 데이터).

사용: python tools/build_pages.py
- rows 가 있는 항목만 채택. menu/price 2개 필드만 내보냄(시청 육안검수용).
- place_id, item_id 순 정렬.
"""
import datetime as dt
import glob
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DRAFTS = ROOT / "storage" / "drafts"
DOCS = ROOT / "docs"


def main():
    items = []
    for f in glob.glob(str(DRAFTS / "*.json")):
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        rows = [{"menu": (r.get("menu") or "").strip(), "price": (r.get("price") or "").strip()}
                for r in d.get("rows", [])
                if (r.get("menu") or "").strip() or (r.get("price") or "").strip()]
        if not rows:
            continue
        items.append({
            "place_id": d.get("place_id"), "title": d.get("title", ""),
            "item_id": d.get("item_id"), "image_url": d.get("image_url", ""),
            "reviewed": bool(d.get("reviewed")), "rows": rows,
        })
    items.sort(key=lambda x: (x["place_id"] or 0, int(x["item_id"]) if str(x["item_id"]).isdigit() else 0))

    bundle = {
        "generated_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "count": len(items),
        "reviewed": sum(1 for i in items if i["reviewed"]),
        "items": items,
    }
    DOCS.mkdir(exist_ok=True)
    (DOCS / "data.json").write_text(json.dumps(bundle, ensure_ascii=False), encoding="utf-8")
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")
    print(f"docs/data.json 생성: {len(items)}개 항목 (검수완료 {bundle['reviewed']}) · {bundle['generated_at']}")


if __name__ == "__main__":
    main()
